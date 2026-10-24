"""Structured messages exchanged between agents (stdlib dataclasses, zero deps)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

FACT, ASSUMPTION = "fact", "assumption"


@dataclass
class ToolResult:
    tool: str
    ok: bool
    data: list[dict] = field(default_factory=list)
    completeness: str = "full"          # full | partial | empty | failed
    error: str | None = None
    attempts: int = 1


@dataclass
class TaskRequest:                      # Critic -> Orchestrator
    agent: str
    kind: str
    params: dict[str, Any]
    reason: str = ""


@dataclass
class Task:
    id: str
    agent: str                          # observability | dependency
    kind: str                           # scan_logs | scan_metrics | topology | changes | past_incidents
    params: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"             # pending | running | done | failed | skipped
    attempts: int = 0
    round: int = 0
    resolved: list[str] = field(default_factory=list)   # services actually scanned
    note: str = ""


@dataclass
class Evidence:
    id: str
    task_id: str | None
    source: str                         # agent that recorded it
    content: str
    kind: str                           # fact | assumption
    category: str = "observation"       # onset|stable|error_log|change|topology|past_incident|gap
    service: str | None = None
    ts: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hypothesis:
    id: str
    statement: str
    category: str
    service: str | None
    confidence: float
    supporting: list[str] = field(default_factory=list)      # evidence ids
    contradicting: list[str] = field(default_factory=list)   # evidence ids
    assumptions: list[str] = field(default_factory=list)


@dataclass
class Critique:
    verdict: str                        # approve | challenge
    issues: list[str] = field(default_factory=list)
    requests: list[TaskRequest] = field(default_factory=list)


@dataclass
class FinalReport:
    outcome: str                        # root_cause_identified | inconclusive
    summary: str
    hypotheses: list[Hypothesis]
    facts: list[str]                    # evidence ids relied upon
    assumptions: list[str]
    open_issues: list[str]
    recommended_actions: list[str]
    termination_reason: str
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
