"""Usage: python run_investigation.py data/incidents/inc_001.json [--llm mock|groq] [--seed N] [--verbose]"""
import argparse, asyncio, json
from incident_agents.orchestrator import Orchestrator
from incident_agents.state import Config
from incident_agents.tools import ToolBox, FailureConfig


def make_llm(kind: str):
    if kind == "groq":
        from incident_agents.llm import GroqLLM
        return GroqLLM()
    if kind != "mock":
        raise ValueError(f"Unknown LLM provider: {kind}")
    from incident_agents.mock_llm import MockLLM
    return MockLLM()


async def run_file(path: str, llm_kind="mock", seed=None, cfg: Config | None = None):
    data = json.load(open(path))
    failures = FailureConfig.from_dict(data.get("failures"))
    if seed is not None:
        failures.seed = seed
    return await Orchestrator(make_llm(llm_kind), ToolBox(data["world"], failures), cfg).investigate(data["incident"])


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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("incident"); ap.add_argument("--llm", choices=("mock", "groq"), default="mock"); ap.add_argument("--seed", type=int)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    print_report(*asyncio.run(run_file(a.incident, a.llm, a.seed)), verbose=a.verbose)
