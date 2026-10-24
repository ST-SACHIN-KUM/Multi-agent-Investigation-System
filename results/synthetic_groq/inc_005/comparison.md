# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 0.0% | 0.0% |
| Ground-truth accuracy (all cases) | 0.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | N/A |
| Tool-call count (total attempts) | 7 | 1 |
| Latency (mean seconds) | 117.402 | 17.695 |
| Token consumption (recorded input + output) | 13007 | 580 |
| Cases | 1 | 1 |
| Successful cases | 0 | 0 |
| Case success rate | 0.0% | 0.0% |
| Outcome accuracy | 100.0% | 0.0% |
| Citation validity | 100.0% | N/A |
| LLM calls | 9 | 1 |
| Input tokens | 10428 | 522 |
| Output tokens | 2579 | 58 |
| Unhandled run errors | 0 | 0 |

Winner by full ground-truth agreement: **tie**.
Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.
Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.
Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.
Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.
Mock results compare different rule-based policies, not real LLM investigation quality.
Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.
This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.
Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific.
