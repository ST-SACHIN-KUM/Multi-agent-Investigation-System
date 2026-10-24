"""Compare both architectures on selected incidents from a dataset."""
import argparse
import asyncio
import csv
import json
import os
import re
import time
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from incident_agents.llm import GroqLLM
from incident_agents.mock_llm import MockLLM
from incident_agents.orchestrator import Orchestrator
from incident_agents.state import Config
from incident_agents.tools import FailureConfig, ToolBox
from single_agent.agent import SingleAgentInvestigator
from single_agent.config import SingleAgentConfig
from single_agent.llm import BaselineMockLLM


class TimedLLM:
    """Apply the same per-request timeout to either architecture."""
    def __init__(self, client, timeout):
        self.client, self.timeout = client, timeout

    @property
    def stats(self):
        return self.client.stats

    async def json(self, role, payload):
        return await asyncio.wait_for(self.client.json(role, payload), self.timeout)


def score_report(report, truth, evidence_ids):
    """Score correctness separately from citation validity (not semantic grounding)."""
    top = report.hypotheses[0] if report.hypotheses else None
    expected = truth.get("expected_outcome", "root_cause_identified")
    eligible = expected == "root_cause_identified" and truth.get("service") is not None
    match = bool(top and top.service == truth.get("service") and top.category == truth.get("category"))
    outcome_correct = report.outcome == expected
    citations = [ref for h in report.hypotheses for ref in h.supporting + h.contradicting]
    invalid = sum(ref not in evidence_ids for ref in citations) + report.stats.get("ungrounded_citations", 0)
    valid = sum(ref in evidence_ids for ref in citations)
    return {
        "expected_outcome": expected, "outcome": report.outcome,
        "expected_service": truth.get("service"), "expected_category": truth.get("category"),
        "predicted_service": top.service if top else None,
        "predicted_category": top.category if top else None,
        "confidence": top.confidence if top else None,
        "root_cause_eligible": eligible,
        "root_cause_correct": match if eligible else None,
        "outcome_correct": outcome_correct,
        "case_success": outcome_correct and (match if eligible else True),
        "valid_citations": valid, "invalid_citations": invalid,
        "citation_validity": valid / (valid + invalid) if valid + invalid else None,
    }


def aggregate(rows):
    summary = {}
    for architecture in ("multi_agent", "single_agent"):
        group = [r for r in rows if r["architecture"] == architecture]
        eligible = [r for r in group if r["root_cause_eligible"]]
        valid, invalid = sum(r["valid_citations"] for r in group), sum(r["invalid_citations"] for r in group)
        summary[architecture] = {
            "root_cause_accuracy": mean(bool(r["root_cause_correct"]) for r in eligible) if eligible else None,
            "evidence_grounding": valid / (valid + invalid) if valid + invalid else None,
            "tool_call_count": sum(r["tool_calls"] for r in group),
            "latency_s": mean(r["latency_s"] for r in group),
            "token_consumption": sum(r["input_tokens"] + r["output_tokens"] for r in group),
            "ground_truth_accuracy": mean(bool(r["case_success"]) for r in group),
            "cases": len(group),
            "successful_cases": sum(bool(r["case_success"]) for r in group),
            "case_success_rate": mean(bool(r["case_success"]) for r in group),
            "root_cause_cases": len(eligible),
            "outcome_accuracy": mean(bool(r["outcome_correct"]) for r in group),
            "citation_validity": valid / (valid + invalid) if valid + invalid else None,
            "errors": sum(r["error"] is not None for r in group),
            "total_tool_calls": sum(r["tool_calls"] for r in group),
            "total_llm_calls": sum(r["llm_calls"] for r in group),
            "total_input_tokens": sum(r["input_tokens"] for r in group),
            "total_output_tokens": sum(r["output_tokens"] for r in group),
            "total_tokens": sum(r["input_tokens"] + r["output_tokens"] for r in group),
            "mean_latency_s": mean(r["latency_s"] for r in group),
        }
    a, b = summary["multi_agent"]["ground_truth_accuracy"], summary["single_agent"]["ground_truth_accuracy"]
    return {"architectures": summary,
            "winner_by_case_success": "tie" if a == b else "multi_agent" if a > b else "single_agent"}


def comparison_metrics(row):
    """Retain the original fields alongside the five metrics and full-answer accuracy."""
    return {**row,
        "root_cause_accuracy": int(bool(row["root_cause_correct"])) if row["root_cause_eligible"] else None,
        "evidence_grounding": row["citation_validity"],
        "tool_call_count": row["tool_calls"], "latency_s": row["latency_s"],
        "token_consumption": row["input_tokens"] + row["output_tokens"],
        "ground_truth_accuracy": int(bool(row["case_success"]))}


async def evaluate(case, architecture, options):
    cfg_args = {"max_tool_calls": options.max_tool_calls, "max_tool_retries": 2,
                "task_timeout": options.llm_timeout, "wall_clock": options.wall_clock}
    cfg = Config(**cfg_args) if architecture == "multi_agent" else SingleAgentConfig(
        **cfg_args, llm_timeout=options.llm_timeout, max_llm_retries=0)
    client = GroqLLM(options.model) if options.llm == "groq" else (
        MockLLM() if architecture == "multi_agent" else BaselineMockLLM())
    llm = TimedLLM(client, options.llm_timeout)
    tools = ToolBox(deepcopy(case["world"]), FailureConfig.from_dict(deepcopy(case.get("failures", {}))))
    agent = Orchestrator(llm, tools, cfg) if architecture == "multi_agent" else SingleAgentInvestigator(llm, tools, cfg)
    started, error, report, state = time.perf_counter(), None, None, None
    try:
        report, state = await asyncio.wait_for(agent.investigate(deepcopy(case["incident"])), options.wall_clock)
    except asyncio.TimeoutError:
        error = "Overall investigation deadline reached"
    except Exception as exc:
        # Do not include provider response bodies or secrets in exported errors.
        error = f"Investigation failed: {type(exc).__name__}"
    finally:
        if options.llm == "groq":
            await client.client.close()
    latency = time.perf_counter() - started
    if report:
        metrics = score_report(report, case["ground_truth"], state.evidence_ids())
    else:
        expected = case["ground_truth"].get("expected_outcome", "root_cause_identified")
        metrics = {"expected_outcome": expected, "outcome": "error",
            "expected_service": case["ground_truth"].get("service"),
            "expected_category": case["ground_truth"].get("category"),
            "predicted_service": None, "predicted_category": None, "confidence": None,
            "root_cause_eligible": expected == "root_cause_identified" and case["ground_truth"].get("service") is not None,
            "root_cause_correct": False if expected == "root_cause_identified" else None,
            "outcome_correct": False, "case_success": False,
            "valid_citations": 0, "invalid_citations": 0, "citation_validity": None}
    # Count every attempted tool call from ToolBox, including errors and retries.
    row = {"incident_id": case["incident"]["id"], "architecture": architecture, **metrics,
           "tool_calls": sum(tools._seen.values()), "llm_calls": llm.stats.calls,
           "input_tokens": llm.stats.input_tokens, "output_tokens": llm.stats.output_tokens,
           "latency_s": round(latency, 4),
           "termination_reason": report.termination_reason if report else "error", "error": error}
    artifact = {"metrics": comparison_metrics(row),
        "diagnostics": {"termination_reason": row["termination_reason"], "error": error,
            "expected_outcome": metrics["expected_outcome"], "outcome": metrics["outcome"]},
        "ground_truth": case["ground_truth"],
        "report": report.to_dict() if report else None,
        "evidence": [asdict(e) for e in state.evidence] if state else [],
        "events": state.events if state else []}
    return row, artifact


def write_outputs(output, rows, metadata):
    table = [comparison_metrics(row) for row in rows]
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]))
        writer.writeheader(); writer.writerows(table)
    summary = {"run": metadata, **aggregate(rows), "measurement_notes": {
        "ground_truth_accuracy": "Exact full-answer correctness: expected outcome must match; conclusive targets also require the correct top service AND category. Inconclusive targets require abstention. Binary per case, averaged across all cases. Same criterion as case_success_rate.",
        "root_cause_accuracy": "Top hypothesis service AND category match ground truth on conclusive-target cases; other cases are N/A. Provider-blocked eligible runs count as incorrect.",
        "evidence_grounding": "Citation-ID validity proxy only: valid references / (valid + invalid references, including removed citations). Semantic claim support is not automatically assessed. No citations = N/A.",
        "tool_call_count": "Total attempted tool calls including retries.",
        "latency_s": "Per-run elapsed seconds; arithmetic mean across selected incidents in the summary.",
        "token_consumption": "Recorded input + output tokens; excludes failed/canceled requests without recorded usage. Mock counts are estimates.",
        "errors": "Exceptions escaping the investigator only; inspect termination_reason and report open_issues for internally handled provider failures.",
    }}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    stats = summary["architectures"]
    def percent(value):
        return f"{value:.1%}" if value is not None else "N/A"
    lines = ["# Architecture comparison", "", f"Mode: {metadata['llm']}; model: {metadata['model']}", "",
             "| Metric | Multi-agent | Single-agent |", "| --- | --- | --- |"]
    for label, key, fmt in [
        ("Root-cause accuracy (conclusive-target cases)", "root_cause_accuracy", percent),
        ("Ground-truth accuracy (all cases)", "ground_truth_accuracy", percent),
        ("Evidence grounding (citation-ID proxy)", "evidence_grounding", percent),
        ("Tool-call count (total attempts)", "tool_call_count", str),
        ("Latency (mean seconds)", "latency_s", lambda x: f"{x:.3f}"),
        ("Token consumption (recorded input + output)", "token_consumption", str),
        ("Cases", "cases", str),
        ("Successful cases", "successful_cases", str),
        ("Case success rate", "case_success_rate", percent),
        ("Outcome accuracy", "outcome_accuracy", percent),
        ("Citation validity", "citation_validity", percent),
        ("LLM calls", "total_llm_calls", str),
        ("Input tokens", "total_input_tokens", str),
        ("Output tokens", "total_output_tokens", str),
        ("Unhandled run errors", "errors", str)]:
        lines.append(f"| {label} | {fmt(stats['multi_agent'][key])} | {fmt(stats['single_agent'][key])} |")
    lines += ["",
        f"Winner by full ground-truth agreement: **{summary['winner_by_case_success']}**.",
        "Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.",
        "Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.",
        "Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.",
        "Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.",
        "Mock results compare different rule-based policies, not real LLM investigation quality.",
        "Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.",
        "This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.",
        "Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific."]
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def select_incidents(value, available=None):
    available = list(available) if available is not None else list(range(1, 11))
    if str(value).lower() == "all":
        return available
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Incident must be one of {available}, or 'all'") from None
    if number not in available:
        raise ValueError(f"Incident must be one of {available}, or 'all'")
    return [number]


def resolve_dataset_path(dataset):
    """Prefer the supplied path, then try a path relative to this script."""
    dataset = Path(dataset).expanduser()
    if not dataset.is_absolute() and not dataset.exists():
        project_path = Path(__file__).resolve().parent / dataset
        if project_path.exists():
            dataset = project_path
    return dataset.resolve()


def load_cases(dataset, selection):
    """Read inputs and join evaluator answers without passing answers to agents."""
    dataset = resolve_dataset_path(dataset)
    directory = dataset / "incidents" if (dataset / "incidents").is_dir() else dataset
    files = {int(match.group(1)): path for path in directory.glob("inc_*.json")
             if (match := re.fullmatch(r"inc_(\d{3})\.json", path.name))}
    if not files:
        raise ValueError(f"No incident files found in {directory}. Pass --dataset with a dataset root containing incidents/inc_001.json.")
    numbers = select_incidents(selection, sorted(files))
    answer_file = dataset / "ground_truth.json"
    if not answer_file.exists() and directory.name == "incidents":
        answer_file = directory.parent / "ground_truth.json"
    answers = json.loads(answer_file.read_text(encoding="utf-8")) if answer_file.exists() else {}
    cases = []
    for number in numbers:
        case = json.loads(files[number].read_text(encoding="utf-8"))
        if "ground_truth" not in case:
            key = case["incident"]["id"]
            if key not in answers:
                raise ValueError(f"Missing evaluator ground truth for {key}")
            case["ground_truth"] = answers[key]
        cases.append(case)
    return numbers, cases


async def run(options):
    dataset = resolve_dataset_path(getattr(options, "dataset", Path(__file__).resolve().parent / "data"))
    numbers, cases = load_cases(dataset, options.incident)
    if options.llm == "groq" and not os.environ.get("GROQ_API_KEY"):
        raise ValueError("Set GROQ_API_KEY before running --llm groq")
    # Keep individually selected incidents separate so their comparison files do
    # not replace results for a different selection in the same output root.
    output = options.output / f"inc_{numbers[0]:03d}" if len(numbers) == 1 else options.output
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    metadata = {"llm": options.llm, "model": options.model if options.llm == "groq" else "deterministic offline policies",
                "wall_clock_s": options.wall_clock, "llm_timeout_s": options.llm_timeout,
                "max_tool_calls": options.max_tool_calls, "max_tool_retries": 2,
                "dataset": str(dataset.resolve()),
                "case_files": [f"inc_{i:03d}.json" for i in numbers]}
    for index, case in enumerate(cases):
        # Alternate execution order to reduce systematic first-run bias.
        order = ("multi_agent", "single_agent") if index % 2 == 0 else ("single_agent", "multi_agent")
        for architecture in order:
            print(f"Running {case['incident']['id']} / {architecture} ...", flush=True)
            row, artifact = await evaluate(case, architecture, options)
            rows.append(row)
            path = output / f"{case['incident']['id']}_{architecture}.json"
            path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            summary = write_outputs(output, rows, metadata) if len({r['architecture'] for r in rows}) == 2 else None
            print(f"  accuracy={comparison_metrics(row)['root_cause_accuracy']}; tools={row['tool_calls']}; latency={row['latency_s']:.2f}s; tokens={row['input_tokens'] + row['output_tokens']}", flush=True)
    print(f"Saved results to {output.resolve()}")
    print("Saved current and restored metrics plus ground-truth accuracy; see comparison.md for definitions.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident", default="1", help="Incident number in the selected dataset, or 'all' (default: 1)")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parent / "data",
                        help="Dataset root containing incidents/ and optional ground_truth.json")
    parser.add_argument("--llm", choices=("mock", "groq"), default="mock")
    parser.add_argument("--model", default=os.environ.get("GROQ_MODEL") or os.environ.get("MODEL") or "qwen/qwen3.8-27b")
    parser.add_argument("--wall-clock", type=float, default=600)
    parser.add_argument("--llm-timeout", type=float, default=90)
    parser.add_argument("--max-tool-calls", type=int, default=40)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "results" /
                        datetime.now(timezone.utc).strftime("comparison_%Y%m%d_%H%M%S_UTC"))
    options = parser.parse_args()
    if options.wall_clock <= 0 or options.llm_timeout <= 0 or options.max_tool_calls < 1:
        parser.error("Timeouts and tool-call budget must be positive")
    try:
        asyncio.run(run(options))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
