import asyncio
import unittest
from copy import deepcopy

from data.make_sample import build_incidents
from incident_agents.llm import BaseLLM
from incident_agents.state import Config
from incident_agents.tools import FailureConfig, ToolBox
from single_agent.agent import SingleAgentInvestigator
from single_agent.llm import BaselineMockLLM
from single_agent.config import SingleAgentConfig


class ScriptedLLM(BaseLLM):
    def __init__(self, responses):
        super().__init__()
        self.responses = iter(responses)
        self.inputs = []

    async def _complete(self, role, payload):
        assert role == "single_agent"
        self.inputs.append(deepcopy(payload))
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value, 10, 5


def tool_request():
    return {"action": "tool", "tool": "query_logs", "args": {"service": "payment-service"}}


def final():
    return {"action": "final", "summary": "Payment degradation", "inconclusive": False,
            "hypotheses": [{"statement": "Payment is failing", "service": "payment-service",
                "category": "service_degradation", "confidence": .8,
                "supporting": ["E1", "E999"], "contradicting": [], "assumptions": []}]}


class SingleAgentBaselineTests(unittest.TestCase):
    def test_timeout_retries_then_recovers(self):
        llm = ScriptedLLM([asyncio.TimeoutError(), tool_request(), final()])
        report, state = self.run_case(llm, cfg=SingleAgentConfig(llm_timeout=.1, backoff_base=0))
        self.assertEqual(report.termination_reason, "agent_finished")
        self.assertEqual(state.tool_calls, 1)
        self.assertEqual(len(llm.inputs), 3)

    def test_timeout_retries_are_bounded(self):
        llm = ScriptedLLM([asyncio.TimeoutError()] * 5)
        report, _ = self.run_case(llm, cfg=SingleAgentConfig(llm_timeout=.1, backoff_base=0))
        self.assertEqual(report.termination_reason, "llm_timeout")
        self.assertEqual(len(llm.inputs), 2)
        self.assertIn("0.1s", " ".join(report.open_issues))

    def test_overall_deadline_cancels_slow_llm(self):
        class SlowLLM(ScriptedLLM):
            async def _complete(self, role, payload):
                self.inputs.append(payload)
                await asyncio.sleep(10)
                return final(), 10, 5
        llm = SlowLLM([])
        report, _ = self.run_case(llm, cfg=SingleAgentConfig(llm_timeout=1, wall_clock=.03, backoff_base=0))
        self.assertEqual(report.termination_reason, "wall_clock_timeout")
        self.assertEqual(len(llm.inputs), 1)

    def run_case(self, llm, failures=None, cfg=None):
        case = build_incidents()[0]
        toolbox = ToolBox(case["world"], FailureConfig.from_dict(failures), latency=0)
        return asyncio.run(SingleAgentInvestigator(llm, toolbox,
            cfg or Config(backoff_base=0)).investigate(case["incident"]))

    def test_single_role_receives_observations_and_no_ground_truth(self):
        llm = ScriptedLLM([tool_request(), final()])
        report, state = self.run_case(llm)
        self.assertEqual(report.outcome, "root_cause_identified")
        self.assertEqual(report.hypotheses[0].supporting, ["E1"])
        self.assertEqual(state.ungrounded_citations, 1)
        self.assertEqual(llm.inputs[0]["observations"], [])
        self.assertTrue(llm.inputs[1]["observations"][0]["result"]["data"])
        self.assertTrue(all("ground_truth" not in p for p in llm.inputs))
        self.assertEqual(report.stats["input_tokens"], 20)

    def test_failed_tool_is_observed_and_cannot_support_conclusion(self):
        llm = ScriptedLLM([tool_request(), final()])
        report, state = self.run_case(llm, {"always_fail": ["query_logs"]})
        self.assertEqual(state.tool_calls, 3)
        self.assertEqual(llm.inputs[1]["observations"][0]["result"]["completeness"], "failed")
        self.assertEqual(report.outcome, "inconclusive")

    def test_tool_budget_is_hard_bound(self):
        llm = ScriptedLLM([tool_request()] * 10)
        report, state = self.run_case(llm, cfg=Config(max_tool_calls=1, backoff_base=0))
        self.assertEqual(state.tool_calls, 1)
        self.assertEqual(report.termination_reason, "tool_budget_exhausted")
        self.assertEqual(report.outcome, "inconclusive")

    def test_llm_failure_still_returns_report(self):
        report, _ = self.run_case(ScriptedLLM([RuntimeError("provider unavailable")]))
        self.assertEqual(report.termination_reason, "llm_failed")
        self.assertEqual(report.outcome, "inconclusive")

    def test_invalid_decisions_cannot_loop_forever(self):
        llm = ScriptedLLM([{"action": "invalid"}] * 10)
        report, state = self.run_case(llm, cfg=Config(max_tool_calls=2))
        self.assertEqual(state.tool_calls, 0)
        self.assertEqual(report.termination_reason, "step_limit_reached")
        self.assertEqual(len(llm.inputs), 4)

    def test_all_ten_incidents_complete_offline(self):
        for case in build_incidents():
            with self.subTest(incident=case["incident"]["id"]):
                cfg = Config(backoff_base=0)
                tools = ToolBox(case["world"], FailureConfig.from_dict(case["failures"]), latency=0)
                report, state = asyncio.run(SingleAgentInvestigator(BaselineMockLLM(), tools, cfg).investigate(case["incident"]))
                self.assertLessEqual(state.tool_calls, cfg.max_tool_calls)
                self.assertIn(report.outcome, ("root_cause_identified", "inconclusive"))
                if case["incident"]["id"] == "INC-010":
                    self.assertEqual(report.outcome, "inconclusive")
