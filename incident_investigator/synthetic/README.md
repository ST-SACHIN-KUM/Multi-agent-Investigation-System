# Synthetic incident dataset

Twelve distinct reproducible scenarios. Agent inputs are in `incidents/`;
evaluator-only answers are in `ground_truth.json`, `ground_answers.csv` (Excel
compatible), and `GROUND_ANSWERS.md` (readable explanations). The answer files
include causal timelines, distractors, conflicts, failure expectations, and actions.
Incident inputs contain no ground-truth field. The comparison runner joins the
answers only for scoring; investigators receive the incident and tool access.

| Number | Scenario | Challenge |
| --- | --- | --- |
| 001 | Database CPU saturation propagating through payment to checkout | Unrelated healthy recommendation release after symptoms; timings differ from 003 |
| 002 | Checkout parser regression | Isolated pre-incident dependency warning |
| 003 | Database CPU saturation | Checkout release after symptoms |
| 004 | Cache eviction storm | Misleading payment incident history |
| 005 | Expired external payment gateway certificate | Normal CPU during connectivity failure |
| 006 | Unreachable configured database endpoint | Healthy process probe versus functional errors |
| 007 | Cache eviction storm propagating through recommendations to checkout | Misleading checkout history and unrelated payment release; timings differ from 004 |
| 008 | Cache eviction storm propagating through recommendations to checkout | Misleading database history and checkout release after symptoms; timings differ from 004 and 007 |
| 009 | Payment handler release exhausts connections | Seeded intermittent tool timeouts |
| 010 | Database CPU saturation with the same causal timeline as 001 | Logs always fail; other responses may be partial; unrelated healthy recommendation release after symptoms |
| 011 | Underdetermined upstream outage | Contradictory probes and missing upstream metrics |
| 012 | Hidden bad payment endpoint | All tools fail; correct observable conclusion is inconclusive |

Run from the `incident_investigator` project directory:

```powershell
python -m synthetic.generate
python compare_agents.py --dataset synthetic --incident 1 --llm mock --output results/synthetic_mock
python compare_agents.py --dataset synthetic --incident all --llm mock --output results/synthetic_mock_all
python compare_agents.py --dataset synthetic --incident 12 --llm groq --output results/synthetic_groq
```

Generation replaces only the twelve numbered inputs and answer files in this
folder. It reuses the existing pure baseline/metric helpers in `data.make_sample`.
Timestamps are simulated minutes; report time is 100. Seeds reproduce metric
noise and tool failures, although different query sequences can encounter
different failures. Tool failure simulation uses the existing unmodified ToolBox.

Accuracy is exact service/category agreement on conclusive-target cases, with
outcome correctness scored separately. Cases 011 and 012 target inconclusive
outcomes; 011 has no uniquely determined ground cause, while 012 has a hidden
cause that cannot be established through the tools. Confidence is not a calibrated
probability and there is no target confidence percentage. Evidence grounding
requires semantic review beyond citation-ID validity. Mock scores measure rule
policies, not model reasoning. Outcome labels describe the intended scenario,
not a guarantee of evidence availability under every stochastic failure sequence.
