# Combined incident comparisons

Copied from the saved synthetic_groq results. Source reports are preserved below; metrics have not been recalculated.

---

## inc_001

Source copy: [comparison.md](source_copies/inc_001/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 100.0% | 0.0% |
| Ground-truth accuracy (all cases) | 100.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | N/A |
| Tool-call count (total attempts) | 13 | 5 |
| Latency (mean seconds) | 285.560 | 47.009 |
| Token consumption (recorded input + output) | 27802 | 9623 |
| Cases | 1 | 1 |
| Successful cases | 1 | 0 |
| Case success rate | 100.0% | 0.0% |
| Outcome accuracy | 100.0% | 0.0% |
| Citation validity | 100.0% | N/A |
| LLM calls | 16 | 5 |
| Input tokens | 22824 | 9299 |
| Output tokens | 4978 | 324 |
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

---

## inc_002

Source copy: [comparison.md](source_copies/inc_002/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 0.0% | 100.0% |
| Ground-truth accuracy (all cases) | 0.0% | 100.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | 100.0% |
| Tool-call count (total attempts) | 9 | 8 |
| Latency (mean seconds) | 299.518 | 77.463 |
| Token consumption (recorded input + output) | 21767 | 16070 |
| Cases | 1 | 1 |
| Successful cases | 0 | 1 |
| Case success rate | 0.0% | 100.0% |
| Outcome accuracy | 100.0% | 100.0% |
| Citation validity | 100.0% | 100.0% |
| LLM calls | 18 | 9 |
| Input tokens | 16863 | 15042 |
| Output tokens | 4904 | 1028 |
| Unhandled run errors | 0 | 0 |

Winner by full ground-truth agreement: **single_agent**.
Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.
Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.
Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.
Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.
Mock results compare different rule-based policies, not real LLM investigation quality.
Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.
This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.
Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific.

---

## inc_003

Source copy: [comparison.md](source_copies/inc_003/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 100.0% | 0.0% |
| Ground-truth accuracy (all cases) | 100.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | N/A |
| Tool-call count (total attempts) | 15 | 0 |
| Latency (mean seconds) | 333.837 | 21.318 |
| Token consumption (recorded input + output) | 37847 | 0 |
| Cases | 1 | 1 |
| Successful cases | 1 | 0 |
| Case success rate | 100.0% | 0.0% |
| Outcome accuracy | 100.0% | 0.0% |
| Citation validity | 100.0% | N/A |
| LLM calls | 21 | 0 |
| Input tokens | 30865 | 0 |
| Output tokens | 6982 | 0 |
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

---

## inc_004

Source copy: [comparison.md](source_copies/inc_004/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 100.0% | 0.0% |
| Ground-truth accuracy (all cases) | 100.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | N/A |
| Tool-call count (total attempts) | 12 | 20 |
| Latency (mean seconds) | 289.315 | 599.996 |
| Token consumption (recorded input + output) | 28850 | 72885 |
| Cases | 1 | 1 |
| Successful cases | 1 | 0 |
| Case success rate | 100.0% | 0.0% |
| Outcome accuracy | 100.0% | 0.0% |
| Citation validity | 100.0% | N/A |
| LLM calls | 18 | 20 |
| Input tokens | 23375 | 71744 |
| Output tokens | 5475 | 1141 |
| Unhandled run errors | 0 | 1 |

Winner by full ground-truth agreement: **multi_agent**.
Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.
Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.
Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.
Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.
Mock results compare different rule-based policies, not real LLM investigation quality.
Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.
This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.
Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific.

---

## inc_005

Source copy: [comparison.md](source_copies/inc_005/comparison.md)

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

---

## inc_006

Source copy: [comparison.md](source_copies/inc_006/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 0.0% | 0.0% |
| Ground-truth accuracy (all cases) | 0.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | N/A | N/A |
| Tool-call count (total attempts) | 6 | 0 |
| Latency (mean seconds) | 4.772 | 0.493 |
| Token consumption (recorded input + output) | 766 | 0 |
| Cases | 1 | 1 |
| Successful cases | 0 | 0 |
| Case success rate | 0.0% | 0.0% |
| Outcome accuracy | 0.0% | 0.0% |
| Citation validity | N/A | N/A |
| LLM calls | 1 | 0 |
| Input tokens | 216 | 0 |
| Output tokens | 550 | 0 |
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

---

## inc_007

Source copy: [comparison.md](source_copies/inc_007/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 0.0% | 0.0% |
| Ground-truth accuracy (all cases) | 0.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | N/A |
| Tool-call count (total attempts) | 12 | 19 |
| Latency (mean seconds) | 375.827 | 600.027 |
| Token consumption (recorded input + output) | 35465 | 73012 |
| Cases | 1 | 1 |
| Successful cases | 0 | 0 |
| Case success rate | 0.0% | 0.0% |
| Outcome accuracy | 100.0% | 0.0% |
| Citation validity | 100.0% | N/A |
| LLM calls | 19 | 19 |
| Input tokens | 28739 | 71873 |
| Output tokens | 6726 | 1139 |
| Unhandled run errors | 0 | 1 |

Winner by full ground-truth agreement: **tie**.
Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.
Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.
Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.
Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.
Mock results compare different rule-based policies, not real LLM investigation quality.
Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.
This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.
Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific.

---

## inc_008

Source copy: [comparison.md](source_copies/inc_008/comparison.md)

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

---

## inc_009

Source copy: [comparison.md](source_copies/inc_009/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 0.0% | 100.0% |
| Ground-truth accuracy (all cases) | 0.0% | 100.0% |
| Evidence grounding (citation-ID proxy) | 100.0% | 100.0% |
| Tool-call count (total attempts) | 25 | 21 |
| Latency (mean seconds) | 262.996 | 292.079 |
| Token consumption (recorded input + output) | 29117 | 35836 |
| Cases | 1 | 1 |
| Successful cases | 0 | 1 |
| Case success rate | 0.0% | 100.0% |
| Outcome accuracy | 100.0% | 100.0% |
| Citation validity | 100.0% | 100.0% |
| LLM calls | 18 | 14 |
| Input tokens | 23931 | 34682 |
| Output tokens | 5186 | 1154 |
| Unhandled run errors | 0 | 0 |

Winner by full ground-truth agreement: **single_agent**.
Ground-truth accuracy requires the expected outcome and, for conclusive targets, the correct service and category. It is the same criterion as case success rate.
Root-cause accuracy compares the top service AND category on conclusive-target cases; other cases are N/A.
Provider-blocked eligible runs count as incorrect; inspect per-run diagnostics before judging model quality.
Evidence grounding uses citation-ID validity as a proxy only; semantic grounding requires manual review of saved reports and evidence.
Mock results compare different rule-based policies, not real LLM investigation quality.
Token usage excludes failed/canceled provider requests not recorded by the shared adapter; mock tokens are estimates.
This is one run per case. Latency and model output can vary; repeat experiments before drawing strong conclusions.
Budgets and model are matched; task structure, context, and recovery behavior remain architecture-specific.

---

## inc_010

Source copy: [comparison.md](source_copies/inc_010/comparison.md)

# Architecture comparison

Mode: groq; model: qwen/qwen3.8-27b

| Metric | Multi-agent | Single-agent |
| --- | --- | --- |
| Root-cause accuracy (conclusive-target cases) | 0.0% | 0.0% |
| Ground-truth accuracy (all cases) | 0.0% | 0.0% |
| Evidence grounding (citation-ID proxy) | N/A | N/A |
| Tool-call count (total attempts) | 15 | 0 |
| Latency (mean seconds) | 52.358 | 0.443 |
| Token consumption (recorded input + output) | 3074 | 0 |
| Cases | 1 | 1 |
| Successful cases | 0 | 0 |
| Case success rate | 0.0% | 0.0% |
| Outcome accuracy | 0.0% | 0.0% |
| Citation validity | N/A | N/A |
| LLM calls | 6 | 0 |
| Input tokens | 1829 | 0 |
| Output tokens | 1245 | 0 |
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
