import asyncio
import json
import unittest
from pathlib import Path

from compare_agents import load_cases
from incident_agents.tools import ToolBox, FailureConfig, ToolTimeout
from synthetic.generate import build_dataset


class SyntheticDatasetTests(unittest.TestCase):
    def test_first_case_is_a_distinct_database_saturation_scenario(self):
        cases, answers = build_dataset()
        first, third = answers["SYN-001"], answers["SYN-003"]
        self.assertEqual(first["service"], third["service"])
        self.assertEqual(first["category"], "resource_exhaustion")
        self.assertEqual(first["expected_outcome"], "root_cause_identified")
        self.assertNotEqual(cases[0]["world"], cases[2]["world"])
        self.assertEqual(cases[0]["incident"]["id"], "SYN-001")
        earliest = {service: min(r["ts"] for r in cases[0]["world"]["logs"] if r["service"] == service)
                    for service in ("postgres-primary", "payment-service", "checkout-api")}
        self.assertLess(earliest["postgres-primary"], earliest["payment-service"])
        self.assertLess(earliest["payment-service"], earliest["checkout-api"])

    def test_reproducible_distinct_inputs_and_withheld_answers(self):
        cases, answers = build_dataset()
        self.assertEqual((cases, answers), build_dataset())
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({json.dumps(c["world"], sort_keys=True) for c in cases}), 12)
        self.assertEqual({c["incident"]["id"] for c in cases}, set(answers))
        for case in cases:
            self.assertNotIn("ground_truth", case)
            services = set(case["world"]["services"])
            for row in case["world"]["logs"] + case["world"]["metrics"] + case["world"]["deployments"]:
                self.assertIn(row["service"], services)
            answer = answers[case["incident"]["id"]]
            self.assertTrue(answer["root_cause"])
            self.assertTrue(answer["causal_timeline"])

    def test_loader_discovers_twelve_and_joins_answers(self):
        root = Path(__file__).resolve().parents[1] / "synthetic"
        numbers, cases = load_cases(root, "all")
        self.assertEqual(numbers, list(range(1, 13)))
        self.assertEqual(len(cases), 12)
        self.assertEqual(load_cases(root, "12")[1][0]["ground_truth"]["expected_outcome"], "inconclusive")
        for n, case in enumerate(build_dataset()[0], 1):
            saved = json.loads((root / "incidents" / f"inc_{n:03d}.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, case)

    def test_permanent_outage_is_enforced_by_shared_tools(self):
        cases, _ = build_dataset()
        case = cases[-1]
        tools = ToolBox(case["world"], FailureConfig.from_dict(case["failures"]), latency=0)
        for tool in tools.TOOLS:
            with self.subTest(tool=tool), self.assertRaises(ToolTimeout):
                asyncio.run(tools.call(tool, {}))
