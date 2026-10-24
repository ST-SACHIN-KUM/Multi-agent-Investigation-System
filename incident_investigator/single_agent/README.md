# Single-agent baseline

One investigator repeatedly chooses a tool call or a final answer. It plans,
interprets raw results, revises hypotheses, checks uncertainty, and writes the
report with one role and one observation history. It does not instantiate or
call Observability, Dependency, Reasoning, Critic, Reporting, or Orchestrator.

```text
Incident -> one agent -> tool request -> shared ToolBox -> observation
                ^                                           |
                +-------------------------------------------+
                |
                +-> final report or bounded inconclusive fallback
```

From the `incident_investigator` project directory:

```powershell
python -m single_agent.run_investigation data/incidents/inc_001.json --llm mock
python -m pip install groq
$env:GROQ_API_KEY = "your-api-key"
python -m single_agent.run_investigation data/incidents/inc_001.json --llm groq --output baseline-report.json
```

The baseline allows 90 seconds per LLM attempt, one retry after a decision timeout,
and 600 seconds overall. These are separate from tool-call timeouts. To allow more
time for a slow provider or larger observation history:

```powershell
python -m single_agent.run_investigation data/incidents/inc_001.json --llm groq --llm-timeout 120 --wall-clock 900 --llm-retries 1
```

`llm_timeout` means the per-decision limit was exhausted after retries;
`wall_clock_timeout` means the overall investigation deadline was reached. Retries
never extend that deadline. Requests canceled locally may still incur provider
usage. Mock runs test this handling but do not diagnose live provider latency.

The usual summary,
leading confidence, assumptions, open issues, actions, and statistics are retained.
`GROQ_MODEL` selects the same model for both architectures (or leave it unset to use
the shared client's default). The baseline imports the existing Groq adapter rather
than maintaining a second provider implementation.

The tools are the exact existing `incident_agents.tools.ToolBox`: logs, metrics,
deployments/configuration, dependencies, and historical incidents, including seeded
timeout/partial/empty failures. Config, evidence models, report models, and data are
also shared. Ground truth is never passed to the agent. Tool observations receive
IDs used by supporting and contradicting citations; historical analogies are not
counted as direct current-incident facts.

Use identical files, failure seeds, model, tool-call/retry/time budgets, and tool
latency for comparison. Both count retry attempts as tool calls.
The baseline now defaults to a longer overall deadline than the multi-agent
configuration: explicitly align `Config.wall_clock` and `SingleAgentConfig.wall_clock`
when benchmarking. Match request timeouts as well where the harness supports them.
Tool failure
sequences can differ when the agents choose different queries. Baseline tool calls
are sequential, whereas the multi-agent scheduler can run independent work in
parallel. The single-agent decision cap is `max_tool_calls + 2`, rather than the
multi-agent critique-round cap. This is an explicit experimental difference.

Statistics include tool calls, LLM decisions, input/output tokens, latency, and
invalid citations. Token totals follow the shared provider's accounting, which
does not include a model request that fails before returning usage through that
adapter. No token spending cap is enforced by either implementation. Existing
citations are validated by ID, not semantically verified against every claim.
Tool availability alone cannot establish factual causation.

Mock mode is a deterministic exploration/scoring policy for offline smoke tests;
it never calls specialist agents. It is not a measure of real model accuracy.
For root-cause accuracy and grounding comparisons, run both with Groq and evaluate
their reports against the withheld ground truth. This folder supplies the baseline,
not a completed comparative benchmark or a claim that one architecture is better.
