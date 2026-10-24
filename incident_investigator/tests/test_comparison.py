import asyncio
import csv
import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from incident_agents.models import FinalReport, Hypothesis
from compare_agents import score_report, select_incidents, run, load_cases, resolve_dataset_path


class ComparisonScoringTests(unittest.TestCase):
    def test_dataset_resolves_from_outside_project(self):
        previous = Path.cwd()
        with TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                numbers, cases = load_cases(Path("synthetic"), "1")
                self.assertEqual(numbers, [1])
                self.assertEqual(cases[0]["incident"]["id"], "SYN-001")
                self.assertEqual(cases[0]["ground_truth"]["category"], "resource_exhaustion")
                self.assertTrue(resolve_dataset_path("synthetic").is_absolute())
            finally:
                os.chdir(previous)

    def test_incidents_directory_can_find_parent_answers(self):
        root = Path(__file__).resolve().parents[1] / "synthetic" / "incidents"
        self.assertEqual(load_cases(root, "12")[1][0]["ground_truth"]["expected_outcome"], "inconclusive")

    def test_incident_selection(self):
        self.assertEqual(select_incidents("1"), [1])
        self.assertEqual(select_incidents("10"), [10])
        self.assertEqual(select_incidents("all"), list(range(1, 11)))
        for value in ("0", "11", "abc", "1,2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                select_incidents(value)

    def test_single_selection_saves_only_two_runs(self):
        with TemporaryDirectory() as temp:
            options = SimpleNamespace(incident="2", llm="mock", model="unused",
                wall_clock=30, llm_timeout=10, max_tool_calls=40, output=Path(temp))
            with redirect_stdout(StringIO()):
                asyncio.run(run(options))
            output = Path(temp) / "inc_002"
            with (output / "comparison.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["incident_id"] for r in rows}, {"INC-002"})
            self.assertEqual({r["architecture"] for r in rows}, {"multi_agent", "single_agent"})
            self.assertTrue({"incident_id", "architecture", "root_cause_accuracy",
                "evidence_grounding", "tool_call_count", "latency_s", "token_consumption",
                "ground_truth_accuracy", "confidence", "expected_service", "predicted_service",
                "outcome_correct", "case_success", "input_tokens", "output_tokens",
                "llm_calls", "termination_reason", "error"} <= set(rows[0]))
            self.assertTrue(all(float(row["ground_truth_accuracy"]) == 1 for row in rows))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["run"]["case_files"], ["inc_002.json"])
            self.assertTrue({"root_cause_accuracy", "evidence_grounding", "tool_call_count",
                "latency_s", "token_consumption", "ground_truth_accuracy", "case_success_rate",
                "outcome_accuracy", "total_input_tokens", "total_output_tokens", "mean_latency_s"}
                <= set(summary["architectures"]["multi_agent"]))
            self.assertEqual(summary["architectures"]["multi_agent"]["ground_truth_accuracy"], 1)
            self.assertEqual(summary["winner_by_case_success"], "tie")
            self.assertEqual(len(list(output.glob("INC-*.json"))), 2)

    def report(self, outcome="root_cause_identified", service="payment-service", category="bad_deploy"):
        return FinalReport(outcome, "Test summary", [Hypothesis("H1", "Candidate", category,
            service, .8, ["E1"], [], [])], ["E1"], [], [], [], "agent_finished")

    def test_conclusive_target_requires_service_category_and_outcome(self):
        truth = {"service": "payment-service", "category": "bad_deploy", "expected_outcome": "root_cause_identified"}
        self.assertTrue(score_report(self.report(), truth, {"E1"})["case_success"])
        self.assertFalse(score_report(self.report(service="checkout-api"), truth, {"E1"})["case_success"])
        self.assertFalse(score_report(self.report(category="bad_config"), truth, {"E1"})["case_success"])
        self.assertFalse(score_report(self.report(outcome="inconclusive"), truth, {"E1"})["case_success"])

    def test_inconclusive_target_does_not_reward_guessing(self):
        truth = {"service": "payment-service", "category": "bad_deploy", "expected_outcome": "inconclusive"}
        metrics = score_report(self.report(outcome="inconclusive"), truth, {"E1"})
        self.assertTrue(metrics["case_success"])
        self.assertIsNone(metrics["root_cause_correct"])
        self.assertFalse(score_report(self.report(), truth, {"E1"})["case_success"])

    def test_citation_validity_accounts_for_removed_references(self):
        report = self.report()
        report.stats["ungrounded_citations"] = 1
        metrics = score_report(report, {"service": "payment-service", "category": "bad_deploy"}, {"E1"})
        self.assertEqual(metrics["citation_validity"], .5)

    def test_no_citations_is_not_perfect_grounding(self):
        report = self.report()
        report.hypotheses = []
        metrics = score_report(report, {"expected_outcome": "inconclusive"}, set())
        self.assertIsNone(metrics["citation_validity"])
