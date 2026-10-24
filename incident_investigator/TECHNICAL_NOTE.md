# Technical note

The system uses six logical agents: Orchestrator, Observability, Dependency,
Reasoning, Critic, and Reporting. This separates evidence collection, causal
analysis, review, and communication. A supervisor coordinates structured tasks
through shared investigation state. Independent tasks run concurrently with
Python asyncio; dependent tasks wait for prerequisites. Critic requests create
additional investigation tasks, allowing conclusions to change as evidence grows.

Dataclasses define tasks, tool results, evidence, hypotheses, critiques, and
reports. Evidence IDs connect hypotheses to supporting and contradicting findings.
Facts, assumptions, and data gaps are recorded separately. Five tools query
simulated logs, metrics, deployments/configuration, service dependencies, and
historical incidents. Seeded failures make timeout and partial-result scenarios
reproducible. Bounded retries, task timeouts, tool-call budgets, and feedback limits
control execution. The comparison runner also enforces an overall deadline.

A single-agent baseline uses the same tools, datasets, provider adapter, and
configured comparison budgets. One role repeatedly selects a tool or final answer,
performing planning, reasoning, and self-review within one observation history.
Ground answers remain outside investigator inputs. Evaluation records root-cause
accuracy, evidence-grounding proxy, tool attempts, latency, and token consumption,
alongside diagnostic metrics.

The multi-agent design provides explicit responsibility boundaries and targeted
criticism, but adds model calls, coordination logic, and opportunities for handoff
errors. Parallel execution can reduce latency while increasing request bursts and
rate-limit exposure. The single-agent design is simpler, but repeatedly sending
raw observations can increase context size, token use, and sequential latency.
Shared-model specialists may retain correlated biases; role separation alone does
not guarantee better reasoning.

Several limitations affect conclusions. Tools access synthetic data rather than
production systems. Mock mode uses deterministic heuristics and cannot establish
real model quality. Evidence grounding currently measures citation-ID validity,
not whether evidence semantically supports a claim. Confidence scores are
uncalibrated. Strict category matching can reject semantically similar answers.
Provider rate limits and deadlines can produce incomplete investigations and
lower accuracy; failed requests may have unrecorded token usage. Saved runs
therefore do not establish a general architecture winner.

Implementation weaknesses also remain: Critic failure becomes approval with a
warning, unresolved review issues do not independently block conclusive reporting,
and planning can silently omit forward dependency references. State is in memory,
and the standalone multi-agent lifecycle lacks a hard global timeout.

Priority improvements are centralized provider-error tracking and rate limiting,
explicit review-unavailable outcomes, stronger evidence-sufficiency gates, and
complete task-graph validation. A predefined cause taxonomy would improve scoring
consistency. Structured observation summaries, duplicate-query detection, and a
reserved reporting budget would reduce single-agent context growth and incomplete
reports. Durable checkpoints would support recovery. Human-reviewed claim-to-evidence
labels would enable semantic grounding evaluation. Repeated experiments across
all scenarios and multiple seeds should report completed-run accuracy together
with end-to-end reliability, exposing infrastructure failures rather than hiding
them or treating them solely as reasoning errors.
