"""Five investigation tools over a simulated world, with seeded, reproducible failures."""
from __future__ import annotations
import asyncio, hashlib, json, random
from dataclasses import dataclass, field
from .models import ToolResult

LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}


class ToolTimeout(Exception):
    """Transient failure: callers may retry."""


class ToolInputError(Exception):
    """Permanent failure: bad arguments, never retried."""


@dataclass
class FailureConfig:
    timeout_p: float = 0.0              # chance a call times out
    partial_p: float = 0.0              # chance results are truncated
    empty_p: float = 0.0                # chance an empty result is returned
    always_fail: list[str] = field(default_factory=list)   # tools that always time out
    seed: int = 0

    @classmethod
    def from_dict(cls, d: dict | None) -> "FailureConfig":
        return cls(**(d or {}))


class ToolBox:
    TOOLS = ("query_logs", "query_metrics", "get_deployments", "get_dependencies", "search_past_incidents")

    def __init__(self, world: dict, failures: FailureConfig | None = None, latency: float = 0.01):
        self.world, self.failures, self.latency = world, failures or FailureConfig(), latency
        self._seen: dict[str, int] = {}

    def _rng(self, tool: str, args: dict, attempt: int) -> random.Random:
        # Deterministic per (seed, tool, args, call number): every retry or re-query gets a fresh roll, reruns are identical.
        sig = json.dumps([tool, args], sort_keys=True, default=str)
        n = self._seen[sig] = self._seen.get(sig, 0) + 1          # nth identical call -> its own roll
        key = json.dumps([self.failures.seed, sig, n], sort_keys=True)
        return random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:16], 16))

    async def call(self, tool: str, args: dict, attempt: int = 1) -> ToolResult:
        if tool not in self.TOOLS:
            raise ToolInputError(f"unknown tool '{tool}'")
        rng = self._rng(tool, args, attempt)
        await asyncio.sleep(self.latency)
        f = self.failures
        if tool in f.always_fail or rng.random() < f.timeout_p:
            raise ToolTimeout(f"{tool} timed out")
        try:
            rows = getattr(self, "_" + tool)(**args)
        except TypeError as e:
            raise ToolInputError(f"bad arguments for {tool}: {e}") from e
        roll = rng.random()
        if roll < f.empty_p:
            return ToolResult(tool, True, [], "empty")
        if roll < f.empty_p + f.partial_p and len(rows) > 1:
            return ToolResult(tool, True, rows[: max(1, len(rows) // 2)], "partial")
        return ToolResult(tool, True, rows, "full" if rows else "empty")

    # ---- implementations (typed inputs, list-of-dict outputs) ----
    def _check_service(self, service: str | None):
        if service is not None and service not in self.world["services"]:
            raise ToolInputError(f"unknown service '{service}'")

    @staticmethod
    def _in_window(ts: int, start, end) -> bool:
        return (start is None or ts >= start) and (end is None or ts <= end)

    def _query_logs(self, service: str, start: int | None = None, end: int | None = None,
                    min_level: str = "WARN", limit: int = 200) -> list[dict]:
        self._check_service(service)
        lo = LEVELS[min_level]
        rows = [r for r in self.world["logs"] if r["service"] == service
                and LEVELS[r["level"]] >= lo and self._in_window(r["ts"], start, end)]
        return sorted(rows, key=lambda r: r["ts"])[:limit]

    def _query_metrics(self, service: str, start: int | None = None, end: int | None = None,
                       metric: str | None = None) -> list[dict]:
        self._check_service(service)
        rows = [r for r in self.world["metrics"] if r["service"] == service
                and (metric is None or r["metric"] == metric) and self._in_window(r["ts"], start, end)]
        return sorted(rows, key=lambda r: (r["metric"], r["ts"]))

    def _get_deployments(self, service: str | None = None, start: int | None = None,
                         end: int | None = None) -> list[dict]:
        self._check_service(service)
        rows = [r for r in self.world["deployments"] if (service is None or r["service"] == service)
                and self._in_window(r["ts"], start, end)]
        return sorted(rows, key=lambda r: r["ts"])

    def _get_dependencies(self, service: str) -> list[dict]:
        self._check_service(service)
        svcs = self.world["services"]
        out = [{"service": d, "relation": "depends_on"} for d in svcs[service].get("depends_on", [])]
        out += [{"service": s, "relation": "depended_on_by"} for s, v in svcs.items()
                if service in v.get("depends_on", [])]
        return out

    def _search_past_incidents(self, keywords: list[str], limit: int = 3) -> list[dict]:
        kws = {k.lower() for k in keywords}
        scored = []
        for inc in self.world["past_incidents"]:
            words = set((inc["summary"] + " " + " ".join(inc.get("tags", []))).lower().replace(",", " ").split())
            score = len(kws & words)
            if score:
                scored.append({**inc, "score": score})
        return sorted(scored, key=lambda r: -r["score"])[:limit]
