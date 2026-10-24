"""The six agents. They communicate only through InvestigationState (evidence, hypotheses, critiques, tasks)."""
from __future__ import annotations
import asyncio
from dataclasses import asdict
from .models import (Task, Hypothesis, Critique, TaskRequest, FinalReport, ToolResult, FACT, ASSUMPTION)
from .tools import ToolBox, ToolTimeout, ToolInputError

TOOL_FOR_KIND = {"scan_logs": "query_logs", "scan_metrics": "query_metrics", "topology": "get_dependencies",
                 "changes": "get_deployments", "past_incidents": "search_past_incidents"}
AGENT_FOR_KIND = {"scan_logs": "observability", "scan_metrics": "observability", "topology": "dependency",
                  "changes": "dependency", "past_incidents": "dependency"}


class BaseAgent:
    name = "agent"

    def __init__(self, llm, state, toolbox: ToolBox | None = None):
        self.llm, self.state, self.toolbox = llm, state, toolbox

    # ---- tool access with bounded retries + exponential backoff ----
    async def call_tool(self, tool: str, args: dict, kind: str, task_params: dict) -> ToolResult:
        st, cfg = self.state, self.state.cfg
        service = args.get("service") or "*"
        res, err = None, None
        for attempt in range(1, cfg.max_tool_retries + 2):
            if st.tool_calls >= cfg.max_tool_calls:
                err = "tool budget exhausted"; break
            st.tool_calls += 1
            try:
                res = await asyncio.wait_for(self.toolbox.call(tool, args, attempt), cfg.tool_timeout)
                res.attempts = attempt
                st.tool_log.append({"tool": tool, "service": service, "attempt": attempt, "completeness": res.completeness})
                break
            except (ToolTimeout, asyncio.TimeoutError) as e:
                err = str(e) or "timeout"
                st.tool_log.append({"tool": tool, "service": service, "attempt": attempt, "completeness": "timeout"})
                st.log(f"{self.name}: {tool}({service}) attempt {attempt} failed: {err}")
                if attempt <= cfg.max_tool_retries:
                    await asyncio.sleep(cfg.backoff_base * 2 ** (attempt - 1))
            except ToolInputError as e:                      # permanent: do not retry
                err = str(e); st.log(f"{self.name}: {tool}({service}) rejected: {err}"); break
        if res is None:
            res = ToolResult(tool, False, [], "failed", err, attempt)
        st.latest_tool[f"{tool}:{service}"] = {"tool": tool, "service": service, "completeness": res.completeness,
                                               "agent": AGENT_FOR_KIND[kind], "kind": kind, "task_params": task_params}
        return res

    def record_gap(self, task: Task, res: ToolResult, service: str | None):
        if res.completeness == "full":
            return
        why = {"failed": f"failed after {res.attempts} attempts ({res.error}); data unavailable",
               "empty": "returned no rows (a genuine absence and a telemetry gap look identical)",
               "partial": "returned truncated results; counts and onsets are lower bounds"}[res.completeness]
        self.state.add_evidence(task_id=task.id, source=self.name, kind=FACT, category="gap", service=service,
                                content=f"{res.tool}({service or '*'}) {why}",
                                meta={"tool": res.tool, "completeness": res.completeness})

    def record_findings(self, task: Task, findings: list[dict]):
        for f in findings:
            if not isinstance(f, dict) or not isinstance(f.get("content"), str):
                continue                                      # malformed LLM output is dropped, never trusted
            kind = f.get("kind") if f.get("kind") in (FACT, ASSUMPTION) else ASSUMPTION
            ts = f.get("ts") if isinstance(f.get("ts"), int) else None
            self.state.add_evidence(task_id=task.id, source=self.name, content=f["content"], kind=kind,
                                    category=f.get("category", "observation"), service=f.get("service"),
                                    ts=ts, meta=f.get("meta") or {})


class ObservabilityAgent(BaseAgent):
    name = "observability"

    def _services(self, task: Task) -> list[str]:
        p = task.params
        if "services" in p:
            return list(p["services"])
        topo = [e for e in self.state.evidence if e.category == "topology" and e.meta.get("service") == p.get("neighbors_of")]
        if not topo:
            self.state.log(f"observability: topology for {p.get('neighbors_of')} missing; scanning degraded (skipped neighbours)")
            return []
        return list(topo[0].meta["neighbors"])

    async def run(self, task: Task):
        p, tool = task.params, TOOL_FOR_KIND[task.kind]
        services = task.resolved = self._services(task)
        window = {"start": p.get("start"), "end": p.get("end")}
        task.note = "" if services else "no services resolved"

        async def one(s):                                      # independent per-service calls run concurrently
            tp = {"services": [s], **window}
            return await self.call_tool(tool, {"service": s, **window}, task.kind, tp)

        results = await asyncio.gather(*(one(s) for s in services))
        for s, r in zip(services, results):
            self.record_gap(task, r, s)
        out = await self.llm.json("observability", {
            "task": {"kind": task.kind, "params": p}, "tool": tool,
            "results": [{"service": s, "completeness": r.completeness, "rows": r.data[:200]} for s, r in zip(services, results)]})
        self.record_findings(task, out.get("findings", []))


class DependencyAgent(BaseAgent):
    name = "dependency"

    async def run(self, task: Task):
        p, tool = task.params, TOOL_FOR_KIND[task.kind]
        if task.kind == "topology":
            args, svc = {"service": p["service"]}, p["service"]
        elif task.kind == "changes":
            args, svc = {"service": p.get("service"), "start": p.get("start"), "end": p.get("end")}, p.get("service")
        else:
            args, svc = {"keywords": p["keywords"]}, None
        res = await self.call_tool(tool, args, task.kind, {k: v for k, v in p.items() if k != "retry"})
        self.record_gap(task, res, svc)
        out = await self.llm.json("dependency", {"task": {"kind": task.kind, "params": p}, "tool": tool,
                                                 "results": [{"service": svc, "completeness": res.completeness, "rows": res.data}]})
        self.record_findings(task, out.get("findings", []))


class ReasoningAgent(BaseAgent):
    name = "reasoning"

    async def run(self) -> list[Hypothesis]:
        st = self.state
        out = await self.llm.json("reasoning", {**st.snapshot_for_llm(),
                                                "previous_hypotheses": [asdict(h) for h in st.hypotheses],
                                                "previous_issues": st.critiques[-1].issues if st.critiques else []})
        valid, hyps = st.evidence_ids(), []
        for i, h in enumerate(out.get("hypotheses", []), 1):
            try:
                cite = lambda k: [x for x in h.get(k, []) if x in valid]
                sup, con = cite("supporting"), cite("contradicting")
                st.ungrounded_citations += (len(h.get("supporting", [])) - len(sup)) + (len(h.get("contradicting", [])) - len(con))
                hyps.append(Hypothesis(id=f"H{i}", statement=str(h["statement"]), category=str(h.get("category", "unknown")),
                                       service=h.get("service"), confidence=max(0.0, min(1.0, float(h["confidence"]))),
                                       supporting=sup, contradicting=con, assumptions=[str(a) for a in h.get("assumptions", [])]))
            except (KeyError, TypeError, ValueError):
                continue
        hyps.sort(key=lambda h: -h.confidence)
        for i, h in enumerate(hyps, 1):
            h.id = f"H{i}"
        st.hypotheses = hyps
        return hyps


class CriticAgent(BaseAgent):
    name = "critic"

    async def run(self) -> Critique:
        st = self.state
        out = await self.llm.json("critic", {**st.snapshot_for_llm(), "hypotheses": [asdict(h) for h in st.hypotheses]})
        reqs = []
        for r in out.get("requests", [])[: st.cfg.max_requests_per_round]:
            if r.get("kind") in TOOL_FOR_KIND and r.get("agent") == AGENT_FOR_KIND[r["kind"]] and isinstance(r.get("params"), dict):
                reqs.append(TaskRequest(r["agent"], r["kind"], r["params"], str(r.get("reason", ""))))
        verdict = "challenge" if reqs else "approve"          # a challenge without actionable requests is just an approval with caveats
        return Critique(verdict, [str(i) for i in out.get("issues", [])], reqs)


class ReportingAgent(BaseAgent):
    name = "reporting"

    async def run(self, termination_reason: str) -> FinalReport:
        st, cfg = self.state, self.state.cfg
        hyps = st.hypotheses
        top = hyps[0] if hyps else None
        margin_ok = top is not None and (len(hyps) < 2 or top.confidence - hyps[1].confidence >= cfg.min_margin)
        conclusive = bool(top) and top.confidence >= cfg.confidence_threshold and margin_ok
        outcome = "root_cause_identified" if conclusive else "inconclusive"
        issues = list(st.critiques[-1].issues) if st.critiques else []
        if top and not margin_ok:
            issues.append("Top hypotheses are not separated by a sufficient margin")
        if top and top.confidence < cfg.confidence_threshold:
            issues.append(f"Top confidence {top.confidence:.2f} is below the {cfg.confidence_threshold:.2f} threshold")
        if not top:
            issues.append("No hypotheses could be formed from the evidence")

        by_id = {e.id: e for e in st.evidence}
        cited = list(dict.fromkeys((top.supporting + top.contradicting) if top else []))
        facts = [i for i in cited if by_id[i].kind == FACT]
        assumptions = [by_id[i].content for i in cited if by_id[i].kind == ASSUMPTION] + (top.assumptions if top else [])
        try:
            narrative = await self.llm.json("reporting", {"outcome": outcome, "top": asdict(top) if top else None,
                                                          "open_issues": issues, "termination_reason": termination_reason,
                                                          "evidence": [asdict(by_id[i]) for i in cited]})
            summary, actions = str(narrative["summary"]), [str(a) for a in narrative["recommended_actions"]]
        except Exception as e:                                 # degrade: structured fields still ship without narrative
            st.log(f"reporting: narrative failed ({e}); using fallback text")
            summary = "Inconclusive (report narrative unavailable)." if not conclusive else f"Probable cause: {top.statement}"
            actions = ["Review the ranked hypotheses and cited evidence manually"]
        return FinalReport(outcome, summary, hyps, facts, list(dict.fromkeys(assumptions)), issues, actions, termination_reason)
