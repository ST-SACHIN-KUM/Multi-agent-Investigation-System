# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 100.0% | 0.0% |
| Ground-truth accuracy (all cases) | 100.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | N/A |
| Tool-call count (total attempts) | 17 | 17 |
| Latency (mean seconds) | 434.771 | 385.246 |
| Token consumption (recorded input + output) | 40378 | 47922 |
| Cases | 1 | 1 |
| Successful cases | 1 | 0 |
| Case success rate | 100.0% | 0.0% |
| Outcome accuracy | 100.0% | 0.0% |
| Citation validity | 100.0% | N/A |
| LLM calls | 21 | 17 |
| Input tokens | 32780 | 46824 |
| Output tokens | 7598 | 1098 |
| Unhandled run errors | 0 | 0 |

Winner by full ground-truth agreement: **multi_agent**.
Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.
Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.
Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.
Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.
Mock results compare different rule-based policies, not real LLM investigation quality.
Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.
This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.
Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific.
