# Setup and run

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram and agent coordination.

This is a runnable command-line implementation of a six-agent production-incident
investigator and a single-agent baseline. Both use the same simulated tools.
Python 3.11 or newer is required. No frontend, database, or monitoring server is
required. Mock mode runs offline; live mode requires Groq access and an API key.

## 1. Open the project directory

Windows PowerShell, using the location in this workspace:

```powershell
cd C:\Users\ksach\Downloads\files\incident_investigator
py -3.11 --version
```

If you copied the project elsewhere, use that directory. The commands below run
from the directory containing `compare_agents.py` and `incident_agents/`.

## 2. Create an environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe --version
```

The commands use the environment's executable directly, so PowerShell activation
and execution-policy changes are unnecessary. On macOS/Linux use `python3.11 -m
venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

## 3. Run offline first

The committed incident files are ready to use; generation is optional.

```powershell
# Six-agent system
.\.venv\Scripts\python.exe run_investigation.py synthetic/incidents/inc_003.json --llm mock

# One-agent baseline, including JSON export
.\.venv\Scripts\python.exe -m single_agent.run_investigation synthetic/incidents/inc_003.json --llm mock --output single_report.json

# Compare both on one incident
.\.venv\Scripts\python.exe compare_agents.py --dataset synthetic --incident 3 --llm mock --output results/setup_mock
```

The investigation commands print a summary, leading-hypothesis confidence,
assumptions, open issues, recommended actions, and execution statistics.
Inconclusive outcomes are valid when evidence cannot establish a cause.
Mock mode follows deterministic rules and verifies execution, not real LLM quality.

## 4. Enable Groq inference

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GROQ_API_KEY = "your-groq-api-key"
$env:GROQ_MODEL = "qwen/qwen3.8-27b"

.\.venv\Scripts\python.exe run_investigation.py synthetic/incidents/inc_003.json --llm groq
.\.venv\Scripts\python.exe -m single_agent.run_investigation synthetic/incidents/inc_003.json --llm groq --output single_report.json
.\.venv\Scripts\python.exe compare_agents.py --dataset synthetic --incident 3 --llm groq --output results/groq_comparison
```

Set the key in the same terminal that runs the commands. The code reads the
environment variable automatically; no source-code edit is needed. `.env` files
are not automatically loaded. Model selection uses an explicit model argument
where supported, then `GROQ_MODEL`, then `MODEL`, then the shared adapter's default.
The example names the current code default, not a guarantee of model availability
or account quota. Choose a model available to your account if necessary.

## 5. Run all cases and inspect saved results

```powershell
# Twelve separate synthetic cases, both architectures
.\.venv\Scripts\python.exe compare_agents.py --dataset synthetic --incident all --llm mock --output results/all_mock

# Live comparison; run when provider capacity is available
.\.venv\Scripts\python.exe compare_agents.py --dataset synthetic --incident all --llm groq --llm-timeout 90 --wall-clock 600 --max-tool-calls 40 --output results/all_groq
```

`--incident` accepts a case number or `all`; the default is 1. Both architectures
run for every selected incident. All twelve means 24 investigations, with multiple
model requests per investigation in live mode.

Output files:

| File | Content |
| --- | --- |
| `comparison.csv` | Excel-compatible per-incident metrics for both architectures |
| `comparison.md` | Aggregate comparison and metric definitions |
| `summary.json` | Machine-readable aggregate results and run settings |
| `SYN-XXX_multi_agent.json` | Multi-agent report, evidence, diagnostics, and events |
| `SYN-XXX_single_agent.json` | Single-agent report, evidence, diagnostics, and events |

A single-case selection saves under a subfolder such as
`results/groq_comparison/inc_003/`. An `all` selection saves directly under the
chosen output folder. Reusing an output folder replaces files with the same names.
Without `--output`, a timestamped project `results/` folder is created. Explicit
relative output paths are relative to your terminal's working directory.

Metrics include root-cause accuracy, evidence grounding (citation-ID validity
proxy), tool attempts, latency, and recorded token consumption. Earlier diagnostic
metrics and ground-truth accuracy are also retained. The evaluator reads the
withheld answers in `synthetic/ground_truth.json`; agents never receive them.
Citation validity is not semantic claim verification. Provider failures affect
scores and may leave unrecorded token usage, so inspect diagnostics before judging
architecture quality.

## 6. Regenerate data and run tests

```powershell
# Optional: overwrite the twelve synthetic inputs and matching answer files
.\.venv\Scripts\python.exe -m synthetic.generate

# Optional: overwrite the original ten sample cases in data/incidents/
.\.venv\Scripts\python.exe data/make_sample.py

# Tests run offline without a key or installed Groq SDK
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

The two datasets are different. Use `--dataset synthetic` for twelve SYN cases;
the default dataset is `data/`, containing ten original INC cases. Existing
comparison files do not update when data changes; rerun the selected cases.

## Troubleshooting and limits

| Symptom | Action |
| --- | --- |
| `No module named groq` | Install requirements using the same environment executable used to run the program |
| Missing API key or authentication failure | Set `GROQ_API_KEY` in that terminal and verify the credential with the provider |
| `RateLimitError` / HTTP 429 | Wait for the provider's retry/quota window; run one case at a time; increasing timeouts alone does not fix quota exhaustion |
| `llm_timeout` | Increase `--llm-timeout` for comparison or single-agent runs; inspect provider availability |
| `wall_clock_timeout` | Increase `--wall-clock` or investigate repeated queries/context growth |
| Relative-import error | Run the single agent with `-m single_agent.run_investigation` from the project directory |
| Dataset not found | Pass the absolute dataset root, or use `--dataset synthetic` with the project runner |
| Python launcher access failure | Use a working local Python 3.11+ installation and recreate the virtual environment |

Tools use simulated JSON records, not live production systems. State is in memory,
semantic evidence grounding is not automated, and provider-blocked runs can be
scored as incorrect. Offline verification does not validate live provider latency
or reasoning. The Groq dependency is unpinned; record the installed SDK version
and exact model when reporting experiment results.

See the [architecture comparison](architecture_comparison/README.md) for design
trade-offs and improvements, and the [synthetic dataset guide](synthetic/README.md)
for scenario descriptions and ground answers.
