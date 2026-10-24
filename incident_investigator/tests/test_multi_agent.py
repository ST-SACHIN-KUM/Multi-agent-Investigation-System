"""Run: python -m unittest -v   (or pytest). No network or API key needed: uses MockLLM."""
import asyncio, json, unittest
from incident_agents.agents import ReasoningAgent
from incident_agents.mock_llm import MockLLM
from incident_agents.orchestrator import Orchestrator
from incident_agents.state import Config, InvestigationState
from incident_agents.tools import ToolBox, FailureConfig, ToolTimeout, ToolInputError

DATA = json.load(open("data/incidents/inc_001.json"))


def run(coro):
    return asyncio.run(coro)


def investigate(world=None, failures=None, cfg=None, llm=None, incident=None):
    tb = ToolBox(world or DATA["world"], FailureConfig.from_dict(failures if failures is not None else DATA["failures"]), latency=0)
    return run(Orchestrator(llm or MockLLM(), tb, cfg or Config(backoff_base=0)).investigate(incident or DATA["incident"]))


class ToolTests(unittest.TestCase):
    def test_deterministic_failures(self):
        f = {"timeout_p": 0.3, "partial_p": 0.3, "seed": 3}
        def outcomes():
            tb = ToolBox(DATA["world"], FailureConfig.from_dict(f), latency=0)
            out = []
            for _ in range(8):
                try:
                    out.append(run(tb.call("query_logs", {"service": "payment-service"})).completeness)
                except ToolTimeout:
                    out.append("timeout")
            return out
        self.assertEqual(outcomes(), outcomes())

    def test_error_handling(self):
        tb = ToolBox(DATA["world"], FailureConfig(always_fail=["query_logs"]), latency=0)
        with self.assertRaises(ToolTimeout):
            run(tb.call("query_logs", {"service": "payment-service"}))
        with self.assertRaises(ToolInputError):
            run(tb.call("get_dependencies", {"service": "nope"}))
        with self.assertRaises(ToolInputError):
            run(tb.call("query_metrics", {"bogus": 1}))
        full = run(ToolBox(DATA["world"], latency=0).call("query_logs", {"service": "payment-service"}))
        part = run(ToolBox(DATA["world"], FailureConfig(partial_p=1.0), latency=0).call("query_logs", {"service": "payment-service"}))
        self.assertEqual(part.completeness, "partial"); self.assertLess(len(part.data), len(full.data))


class StateTests(unittest.TestCase):
    def test_dependencies_and_dedup(self):
        st = InvestigationState(DATA["incident"], Config())
        a = st.add_task("dependency", "topology", {"service": "x"})
        b = st.add_task("observability", "scan_logs", {"services": ["x"]}, [a.id])
        self.assertIsNone(st.add_task("dependency", "topology", {"service": "x"}))
        self.assertEqual([t.id for t in st.ready_tasks()], [a.id])
        a.status = "failed"                                   # failed dependency => dependent runs degraded
        self.assertEqual([t.id for t in st.ready_tasks()], [b.id])

    def test_evidence_dedup(self):
        st = InvestigationState(DATA["incident"], Config())
        kw = dict(task_id=None, source="t", content="same", kind="fact", category="x", service="s")
        self.assertEqual(st.add_evidence(**kw), st.add_evidence(**kw))


class EndToEnd(unittest.TestCase):
    def test_finds_root_cause_despite_red_herring_and_failures(self):
        report, st = investigate()
        self.assertEqual(report.outcome, "root_cause_identified")
        self.assertEqual(report.hypotheses[0].service, "payment-service")
        self.assertEqual(report.stats["ungrounded_citations"], 0)
        self.assertGreater(report.hypotheses[0].confidence, report.hypotheses[1].confidence + 0.5)

    def test_not_keyed_to_names(self):                        # same structure, renamed services: still works
        raw = json.dumps(DATA).replace("payment-service", "ledger-svc").replace("checkout-api", "front-door")
        d = json.loads(raw)
        report, _ = investigate(d["world"], d["failures"], incident=d["incident"])
        self.assertEqual(report.hypotheses[0].service, "ledger-svc")

    def test_critic_feedback_loop_adds_tasks(self):
        report, st = investigate()
        self.assertGreaterEqual(report.stats["rounds"], 1)
        self.assertTrue(any(t.round >= 1 for t in st.tasks.values()))

    def test_inconclusive_when_all_telemetry_down(self):
        report, _ = investigate(failures={"always_fail": list(ToolBox.TOOLS)})
        self.assertEqual(report.outcome, "inconclusive")
        self.assertTrue(report.open_issues)

    def test_bounded_retries_and_budget(self):
        report, st = investigate(failures={"always_fail": ["query_logs"]}, cfg=Config(backoff_base=0, max_tool_retries=2, max_tool_calls=15))
        self.assertLessEqual(st.tool_calls, 15)
        log_attempts = [c for c in st.tool_log if c["tool"] == "query_logs" and c["service"] == "checkout-api"]
        self.assertTrue(all(c["attempt"] <= 3 for c in log_attempts))
        self.assertIn(report.stats["termination_reason"], {"critic_approved", "max_rounds_reached", "tool_budget_exhausted", "no_new_evidence_available"})

    def test_tiny_budget_still_reports(self):
        report, st = investigate(cfg=Config(backoff_base=0, max_tool_calls=3))
        self.assertLessEqual(st.tool_calls, 3)
        self.assertIsNotNone(report.outcome)

    def test_recovers_from_reasoning_agent_crash(self):
        orig = ReasoningAgent.run
        async def boom(self): raise RuntimeError("reasoner down")
        ReasoningAgent.run = boom
        try:
            report, _ = investigate()
        finally:
            ReasoningAgent.run = orig
        self.assertEqual(report.outcome, "inconclusive")      # degraded, not crashed

    def test_hallucinated_citations_are_dropped(self):
        class Liar(MockLLM):
            def _reasoning(self, p):
                out = super()._reasoning(p)
                for h in out["hypotheses"]:
                    h["supporting"] += ["E999"]
                return out
        report, st = investigate(llm=Liar())
        self.assertGreater(st.ungrounded_citations, 0)
        valid = st.evidence_ids()
        self.assertTrue(all(i in valid for h in report.hypotheses for i in h.supporting + h.contradicting))

    def test_independent_tasks_run_in_parallel(self):
        tb = ToolBox(DATA["world"], latency=0.05)
        t0 = asyncio.get_event_loop_policy()  # noqa
        import time; s = time.perf_counter()
        run(Orchestrator(MockLLM(), tb, Config(backoff_base=0)).investigate(DATA["incident"]))
        serial_floor = 0.05 * 10                              # >=10 tool calls; sequential would take >= 0.5s
        self.assertLess(time.perf_counter() - s, serial_floor)


if __name__ == "__main__":
    unittest.main()
