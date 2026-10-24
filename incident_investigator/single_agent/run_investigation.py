"""Run as a module or directly: python single_agent/run_investigation.py ..."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Direct file execution puts single_agent/ on sys.path, not its parent.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from incident_agents.tools import FailureConfig, ToolBox
from single_agent.agent import SingleAgentInvestigator
from single_agent.config import SingleAgentConfig
from single_agent.llm import make_llm

async def run_file(path, llm_kind="mock", seed=None, cfg=None):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    failures = FailureConfig.from_dict(data.get("failures"))
    if seed is not None:
        failures.seed = seed
    return await SingleAgentInvestigator(make_llm(llm_kind), ToolBox(data["world"], failures), cfg).investigate(data["incident"])

def print_report(report, state, verbose=False):
    print(f"\n=== {state.incident['id']}: {report.outcome.upper()} ({report.termination_reason}) ===")
    print(f"Summary: {report.summary}")
    top = max(report.hypotheses, key=lambda h: h.confidence, default=None)
    print(f"Confidence score (leading hypothesis): {top.confidence:.0%}" if top else "Confidence score: N/A (no hypothesis)")
    # if verbose:
    #     by_id = {e.id: e for e in state.evidence}
    #     for h in report.hypotheses:
    #         print(f"\n  {h.id} [{h.confidence:.2f}] {h.category} @ {h.service}: {h.statement}")
    #         for i in h.supporting:
    #             print(f"      + {i} ({by_id[i].kind}) {by_id[i].content}")
    #         for i in h.contradicting:
    #             print(f"      - {i} ({by_id[i].kind}) {by_id[i].content}")
    print("\nAssumptions:", *(f"\n  ~ {a}" for a in report.assumptions) or ["none"])
    print("Open issues:", *(f"\n  ! {i}" for i in report.open_issues) or ["none"])
    print("Recommended actions:", *(f"\n  > {a}" for a in report.recommended_actions))
    print("\nStats:", json.dumps(report.stats))
    # if verbose:
    #     print("\n--- event log ---", *state.events, sep="\n")
    
    
def main():
    parser = argparse.ArgumentParser(description="Single-agent incident investigation")
    parser.add_argument("incident")
    parser.add_argument("--llm", choices=("mock", "groq"), default="mock")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--llm-timeout", type=float, default=90, help="Seconds per LLM decision attempt (default: 90)")
    parser.add_argument("--wall-clock", type=float, default=600, help="Overall investigation limit in seconds (default: 600)")
    parser.add_argument("--llm-retries", type=int, default=1, help="Retries after an LLM decision timeout (default: 1)")
    args = parser.parse_args()
    try:
        cfg = SingleAgentConfig(llm_timeout=args.llm_timeout, wall_clock=args.wall_clock,
                                max_llm_retries=args.llm_retries)
    except ValueError as exc:
        parser.error(str(exc))
    report, state = asyncio.run(run_file(args.incident, args.llm, args.seed, cfg))
    print_report(report, state, args.verbose)
    if args.output:
        args.output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
