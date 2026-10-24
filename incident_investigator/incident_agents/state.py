"""Shared investigation state: task graph, evidence, hypotheses, budgets, event log."""
from __future__ import annotations
import json, time
from dataclasses import dataclass, asdict
from .models import Task, Evidence, Hypothesis, Critique


@dataclass
class Config:
    max_rounds: int = 3                 # critic -> orchestrator feedback loops
    max_tool_calls: int = 40            # hard budget across all agents
    max_tool_retries: int = 2           # per tool call (so up to 3 attempts)
    max_task_retries: int = 1           # per task (agent-level failure)
    max_parallel: int = 4
    max_requests_per_round: int = 4
    backoff_base: float = 0.02          # seconds, doubled each retry
    tool_timeout: float = 5.0
    task_timeout: float = 30.0
    wall_clock: float = 120.0
    lookback: int = 120                 # minutes before report time to investigate
    confidence_threshold: float = 0.6   # below this the outcome is "inconclusive"
    min_margin: float = 0.1             # top-1 must beat top-2 by this much


class InvestigationState:
    """asyncio is single-threaded, so mutations that don't `await` midway are atomic (no locks needed)."""

    def __init__(self, incident: dict, cfg: Config):
        self.incident, self.cfg = incident, cfg
        self.tasks: dict[str, Task] = {}
        self.evidence: list[Evidence] = []
        self.hypotheses: list[Hypothesis] = []
        self.critiques: list[Critique] = []
        self.tool_calls = 0
        self.tool_log: list[dict] = []
        self.latest_tool: dict[str, dict] = {}   # "tool:service" -> most recent outcome (for open-gap tracking)
        self.events: list[str] = []
        self.round = 0
        self.started = time.perf_counter()
        self.ungrounded_citations = 0
        self._n = {"T": 0, "E": 0}

    # ---- helpers ----
    def log(self, msg: str):
        self.events.append(f"[{time.perf_counter() - self.started:6.2f}s r{self.round}] {msg}")

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def out_of_budget(self) -> str | None:
        if self.tool_calls >= self.cfg.max_tool_calls:
            return "tool_budget_exhausted"
        if self.elapsed() >= self.cfg.wall_clock:
            return "wall_clock_timeout"
        return None

    @property
    def window(self) -> dict:
        end = self.incident["reported_at"]
        return {"start": max(0, end - self.cfg.lookback), "end": end}

    # ---- task graph ----
    def add_task(self, agent: str, kind: str, params: dict, depends_on: list[str] | None = None) -> Task | None:
        sig = (agent, kind, json.dumps(params, sort_keys=True))
        if any((t.agent, t.kind, json.dumps(t.params, sort_keys=True)) == sig for t in self.tasks.values()):
            return None                 # duplicate work is never scheduled twice
        self._n["T"] += 1
        t = Task(f"T{self._n['T']}", agent, kind, params, depends_on or [], round=self.round)
        self.tasks[t.id] = t
        return t

    def ready_tasks(self) -> list[Task]:
        done = {"done", "failed", "skipped"}   # failed deps -> run degraded rather than deadlock
        return [t for t in self.tasks.values()
                if t.status == "pending" and all(self.tasks[d].status in done for d in t.depends_on)]

    def pending(self) -> list[Task]:
        return [t for t in self.tasks.values() if t.status == "pending"]

    # ---- evidence ----
    def add_evidence(self, **kw) -> str:
        for e in self.evidence:          # identical findings from re-scans are merged, not double counted
            if (e.category, e.service, e.content, e.kind) == (kw.get("category", "observation"), kw.get("service"), kw["content"], kw["kind"]):
                return e.id
        self._n["E"] += 1
        e = Evidence(id=f"E{self._n['E']}", **kw)
        self.evidence.append(e)
        return e.id

    def evidence_ids(self) -> set[str]:
        return {e.id for e in self.evidence}

    def open_gaps(self) -> list[dict]:
        return [v for v in self.latest_tool.values() if v["completeness"] != "full"]

    def snapshot_for_llm(self) -> dict:
        return {"incident": self.incident, "window": self.window, "round": self.round,
                "max_rounds": self.cfg.max_rounds,
                "evidence": [asdict(e) for e in self.evidence],
                "open_gaps": self.open_gaps(),
                "tasks_done": [{"agent": t.agent, "kind": t.kind, "services": t.resolved,
                                "status": t.status} for t in self.tasks.values()]}
