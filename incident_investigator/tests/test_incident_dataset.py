"""Dataset integrity and bounded end-to-end execution, without external APIs."""
import asyncio
import json
import unittest
from pathlib import Path

from data.make_sample import build_incidents
from incident_agents.mock_llm import MockLLM
from incident_agents.orchestrator import Orchestrator
from incident_agents.state import Config
from incident_agents.tools import FailureConfig, ToolBox


class IncidentDatasetTests(unittest.TestCase):
    def test_ten_distinct_reproducible_worlds(self):
        cases = build_incidents()
        self.assertEqual(cases, build_incidents())
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({c["incident"]["id"] for c in cases}), 10)
        self.assertEqual(len({json.dumps(c["world"], sort_keys=True) for c in cases}), 10)
        for case in cases:
            with self.subTest(incident=case["incident"]["id"]):
                world = case["world"]
                services = set(world["services"])
                self.assertIn(case["incident"]["affected_service"], services)
                for row in world["logs"] + world["metrics"] + world["deployments"]:
                    self.assertIn(row["service"], services)
                    self.assertLessEqual(row["ts"], case["incident"]["reported_at"])
                for spec in world["services"].values():
                    self.assertTrue(set(spec["depends_on"]) <= services)

    def test_generated_files_match_builders(self):
        directory = Path(__file__).resolve().parents[1] / "data" / "incidents"
        for n, case in enumerate(build_incidents(), 1):
            with self.subTest(incident=n):
                saved = json.loads((directory / f"inc_{n:03d}.json").read_text(encoding="utf-8"))
                self.assertEqual(saved, case)

    def test_all_cases_complete_with_valid_citations_and_bounded_calls(self):
        for case in build_incidents():
            with self.subTest(incident=case["incident"]["id"]):
                cfg = Config(backoff_base=0)
                tools = ToolBox(case["world"], FailureConfig.from_dict(case["failures"]), latency=0)
                report, state = asyncio.run(
                    Orchestrator(MockLLM(), tools, cfg).investigate(case["incident"])
                )
                self.assertLessEqual(state.tool_calls, cfg.max_tool_calls)
                self.assertIn(report.outcome, ("root_cause_identified", "inconclusive"))
                for hypothesis in report.hypotheses:
                    self.assertTrue(set(hypothesis.supporting + hypothesis.contradicting) <= state.evidence_ids())
                if case["incident"]["id"] == "INC-010":
                    self.assertEqual(report.outcome, "inconclusive")
                    self.assertTrue(report.open_issues)
