# Multi-agent incident investigator

The [technical note](TECHNICAL_NOTE.md) summarizes key decisions, trade-offs,
limitations, and potential improvements in fewer than 500 words.

The [architecture diagram and coordination guide](ARCHITECTURE.md) describes the
six agents, shared state, parallel scheduling, structured handoffs, and feedback.

Start with [SETUP.md](SETUP.md) for environment setup, offline and Groq commands,
single-agent and multi-agent execution, comparison outputs, and troubleshooting.

Quick offline run from this directory (Python 3.11+):

```powershell
python run_investigation.py synthetic/incidents/inc_003.json --llm mock
python -m single_agent.run_investigation synthetic/incidents/inc_003.json --llm mock
python compare_agents.py --dataset synthetic --incident 3 --llm mock --output results/quickstart
```

See [the architecture comparison](architecture_comparison/README.md) for workflow
diagrams, saved Groq-run observations, trade-offs, metric limitations, and proposed
improvements for both the multi-agent and single-agent systems.

Comparison output retains five core measurements: root-cause accuracy,
evidence grounding (citation-ID validity proxy, not semantic verification),
tool-call count, latency, and recorded input-plus-output token consumption.
CSV also restores earlier fields: confidence, expected/predicted values, outcome
correctness, case success, citation counts, tool/LLM calls, separate input/output
tokens, termination reason, and errors.
Summary tool calls and tokens are totals; summary latency is a mean. Accuracy is
top service/category agreement on conclusive-target cases; other cases are N/A.
`ground_truth_accuracy` checks the full expected answer: outcome plus service and
category for conclusive targets; appropriate abstention for inconclusive targets.
It is 0/1 per incident and averaged across all incidents in the summary, using the
same criterion as the restored case-success rate. Root-cause accuracy retains its
separate definition and denominator. Earlier aggregate metrics and the case-success
winner are restored alongside the current metrics. Confidence remains separate
from measured correctness. Detailed reports retain diagnostic information.
Old result files retain their previous format until you rerun the comparison.

A separate twelve-case benchmark with withheld ground answers is available in
[`synthetic/README.md`](synthetic/README.md). To use it:

```powershell
python compare_agents.py --dataset synthetic --incident 1 --llm groq --output results/synthetic_groq
```

Use `--incident all` to compare all twelve cases. Ground answers are in
`synthetic/ground_truth.json`, `synthetic/ground_answers.csv`, and
`synthetic/GROUND_ANSWERS.md`; they are not included in agent inputs.

## Compare selected incidents

From this project directory:

```powershell
python compare_agents.py --incident 1 --llm mock --output results/mock_comparison
$env:GROQ_API_KEY = "your-api-key"
python compare_agents.py --incident 1 --llm groq --output results/groq_comparison
python compare_agents.py --incident all --llm groq --output results/groq_all
```

Both architectures use identical case data, model, failure seeds, and configured
tool-call/time budgets. `--incident 1` runs only `inc_001.json` with both
architectures. Choose any number from 1 through 10; the default is 1. All ten
run only when `--incident all` is explicitly provided. Individual selections
save into a subfolder such as `results/groq_comparison/inc_001`, preserving other
incidents' results. Re-running the same incident in that folder replaces its
previous result files.

The runner saves `comparison.csv` (two rows per selected incident),
`comparison.md` (readable aggregate), `summary.json`, and two full report/evidence
JSON files per incident. Results are saved after each completed run. An investigation failure
is recorded rather than stopping the batch. Pass `--model`, `--llm-timeout`,
`--wall-clock`, or `--max-tool-calls` to configure the experiment. With no output
option, a timestamped directory under `results` is created.

Case success requires the expected outcome and, on conclusive-target cases, the
correct leading service and cause category. Inconclusive-target cases require
abstention. Root-cause accuracy measures the leading hypothesis on the seven
conclusive-target cases, even if the report abstains; it is therefore distinct
from case success. Citation validity checks reference IDs, not semantic grounding.
Full reports and evidence are saved for manual grounding review. Mock results
compare offline heuristics; use Groq for model-quality evaluation. Recorded tokens
exclude failed/canceled provider requests without recorded usage. This script
does not estimate monetary costs. Running Groq makes billable API requests as
applicable to your plan. Repeat runs to assess variation.

## Setup
Python 3.11+. Mock mode needs no installs. For a real LLM: `pip install groq`, set `GROQ_API_KEY`.

PowerShell setup:

```powershell
pip install groq
$env:GROQ_API_KEY = "your-groq-api-key"
$env:GROQ_MODEL = "qwen/qwen3.8-27b"  # optional; current code default
```

Model selection: explicit constructor argument, then `GROQ_MODEL`, then `MODEL` (legacy fallback), then the default above.
The client uses Groq's asynchronous chat completions API with JSON object mode: https://console.groq.com/docs/text-chat

## Run
    python data/make_sample.py                                   # regenerate all ten incidents
    python run_investigation.py data/incidents/inc_001.json --verbose
    python run_investigation.py data/incidents/inc_001.json --llm groq
    python -m unittest discover -s tests -t . -v

## Synthetic scenarios

`data/make_sample.py` writes `inc_001.json` through `inc_010.json` into its own
`data/incidents` directory, independent of the terminal's working directory.
Re-running it replaces those ten generated files; other files are left alone.

| Incident | Scenario / challenge |
| --- | --- |
| 001 | Payment pool reduction, unrelated deployment, intermittent tool failures |
| 002 | Checkout parser regression with healthy dependencies |
| 003 | Database resource exhaustion propagating downstream |
| 004 | Cache eviction storm with misleading historical analogy |
| 005 | Checkout deployment after the actual payment failure |
| 006 | Broken payment configuration despite normal CPU |
| 007 | Conflicting probes with insufficient evidence to distinguish causes |
| 008 | Payment deployment with intermittent tool timeouts |
| 009 | Payment degradation with persistent truncated telemetry |
| 010 | All investigation tools unavailable |

Seeds make generated noise and simulated failures reproducible. `ground_truth`
is evaluator-only metadata and is never passed to the agents. Its
`expected_outcome` records whether the accessible evidence should support a
conclusion, separately from the hidden causal service/category. Cases 007,
009, and 010 target inconclusive outcomes. Offline smoke tests verify execution,
budgets, and citation integrity; they do not establish accuracy for all cases.

Run an individual scenario:

    python run_investigation.py data/incidents/inc_003.json --llm mock --verbose

## Layout
- `incident_agents/models.py`   structured messages (Evidence, Hypothesis, Critique, TaskRequest, FinalReport)
- `incident_agents/tools.py`    5 tools + seeded timeout/partial/empty failures
- `incident_agents/state.py`    shared state, task graph, budgets
- `incident_agents/agents.py`   Observability, Dependency, Reasoning, Critic, Reporting
- `incident_agents/orchestrator.py` planning, parallel waves, critic loop, termination, recovery
- `incident_agents/llm.py` / `mock_llm.py`  Groq client / deterministic offline stand-in

## Known limitations
- Live Groq API calls require the SDK and an API key; offline tests do not measure real model quality.
- Mock reasoning is rule-based, so it tests orchestration, not LLM quality.
- Dataclasses instead of Pydantic to keep zero dependencies.
- The comparison harness is `compare_agents.py`; its metrics and limitations are
  described in [SETUP.md](SETUP.md) and the architecture comparison.

## Single-agent baseline

The baseline uses the same tools and incident files with one investigating agent:

    python -m single_agent.run_investigation data/incidents/inc_001.json --llm mock
    python -m single_agent.run_investigation data/incidents/inc_001.json --llm groq

Pass `--output baseline-report.json` to export its report for evaluation.
