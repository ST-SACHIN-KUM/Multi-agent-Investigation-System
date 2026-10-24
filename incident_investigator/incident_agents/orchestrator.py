"""Orchestrator: plans, schedules tasks in parallel, runs the critic feedback loop, enforces limits."""
from __future__ import annotations
import asyncio
from .agents import (ObservabilityAgent, DependencyAgent, ReasoningAgent, CriticAgent, ReportingAgent,
                     TOOL_FOR_KIND, AGENT_FOR_KIND)
from .models import FinalReport, Task, Critique
from .state import Config, InvestigationState
from .tools import ToolBox


class Orchestrator:
    def __init__(self, llm, toolbox: ToolBox, cfg: Config | None = None):
        self.llm, self.toolbox, self.cfg = llm, toolbox, cfg or Config()

    async def investigate(self, incident: dict) -> tuple[FinalReport, InvestigationState]:
        st = self.state = InvestigationState(incident, self.cfg)
        self.workers = {"observability": ObservabilityAgent(self.llm, st, self.toolbox),
                        "dependency": DependencyAgent(self.llm, st, self.toolbox)}
        reasoner, critic, reporter = ReasoningAgent(self.llm, st), CriticAgent(self.llm, st), ReportingAgent(self.llm, st)

        await self._plan()
        reason = "max_rounds_reached"
        for rnd in range(self.cfg.max_rounds + 1):
            st.round = rnd
            await self._run_ready()
            try:
                hyps = await reasoner.run()
                st.log(f"reasoning: {len(hyps)} hypotheses, top={hyps[0].service if hyps else None} "
                       f"({hyps[0].confidence if hyps else 0})")
            except Exception as e:                             # recovery: keep previous hypotheses, continue
                st.log(f"reasoning FAILED ({type(e).__name__}: {e}); keeping previous hypotheses")
            try:
                crit = await critic.run()
            except Exception as e:                             # recovery: no critic means we stop with caveats
                st.log(f"critic FAILED ({type(e).__name__}: {e}); terminating with caveat")
                crit = Critique("approve", ["Critic unavailable: conclusions were not challenged"])
            st.critiques.append(crit)
            st.log(f"critic: {crit.verdict}; issues={len(crit.issues)} requests={len(crit.requests)}")
            if crit.verdict == "approve":
                reason = "critic_approved"; break
            if rnd == self.cfg.max_rounds:
                reason = "max_rounds_reached"; break
            if (b := st.out_of_budget()):
                reason = b; break
            st.round = rnd + 1
            if not self._enqueue(crit):
                reason = "no_new_evidence_available"; break
        for t in st.pending():
            t.status = "skipped"
        report = await reporter.run(reason)
        report.stats = self._stats(reason)
        return report, st

    # ---- planning ----
    async def _plan(self):
        st = self.state
        try:
            plan = (await self.llm.json("orchestrator", {"incident": st.incident, "window": st.window}))["tasks"]
            keys: dict[str, str] = {}
            for spec in plan:
                if spec["kind"] not in TOOL_FOR_KIND or AGENT_FOR_KIND[spec["kind"]] != spec["agent"]:
                    continue
                deps = [keys[k] for k in spec.get("depends_on", []) if k in keys]
                t = st.add_task(spec["agent"], spec["kind"], spec["params"], deps)
                if t:
                    keys[spec["key"]] = t.id
            if not st.tasks:
                raise ValueError("empty plan")
        except Exception as e:                                 # recovery: fall back to a minimal safe plan
            st.log(f"planning FAILED ({e}); using fallback plan")
            svc, w = st.incident["affected_service"], st.window
            st.add_task("dependency", "changes", dict(w))
            st.add_task("observability", "scan_logs", {"services": [svc], **w})
            st.add_task("observability", "scan_metrics", {"services": [svc], **w})
        st.log(f"plan: {[(t.id, t.kind, t.depends_on) for t in st.tasks.values()]}")

    # ---- scheduling (parallel waves honouring task dependencies) ----
    async def _run_ready(self):
        st = self.state
        while (ready := st.ready_tasks()):
            if st.out_of_budget():
                break
            batch = ready[: self.cfg.max_parallel]
            st.log(f"running in parallel: {[t.id + ':' + t.kind for t in batch]}")
            await asyncio.gather(*(self._execute(t) for t in batch))

    async def _execute(self, task: Task):
        st, worker = self.state, self.workers[task.agent]
        task.status = "running"
        for attempt in range(1, self.cfg.max_task_retries + 2):
            task.attempts = attempt
            try:
                await asyncio.wait_for(worker.run(task), self.cfg.task_timeout)
                task.status = "done"
                return
            except Exception as e:                             # agent-level failure: bounded retry, then degrade
                st.log(f"{task.id} ({task.kind}) attempt {attempt} failed: {type(e).__name__}: {e}")
                await asyncio.sleep(self.cfg.backoff_base * 2 ** (attempt - 1))
        task.status = "failed"
        st.add_evidence(task_id=task.id, source="orchestrator", kind="fact", category="gap",
                        content=f"Task {task.kind} {task.params} failed after {task.attempts} attempts; evidence missing",
                        meta={"tool": TOOL_FOR_KIND[task.kind], "completeness": "failed"})

    # ---- critic feedback -> new tasks ----
    def _enqueue(self, crit: Critique) -> int:
        st, added = self.state, 0
        for r in crit.requests:
            if st.out_of_budget():
                break
            t = st.add_task(r.agent, r.kind, r.params)
            if t:
                added += 1
                st.log(f"new task {t.id} {t.kind} {r.params.get('services', r.params)} <- critic: {r.reason}")
        return added

    def _stats(self, reason: str) -> dict:
        s, l = self.state, self.llm.stats
        return {"termination_reason": reason, "rounds": s.round, "tool_calls": s.tool_calls,
                "llm_calls": l.calls, "input_tokens": l.input_tokens, "output_tokens": l.output_tokens,
                "latency_s": round(s.elapsed(), 3), "ungrounded_citations": s.ungrounded_citations,
                "tasks": {k: sum(t.status == k for t in s.tasks.values()) for k in ("done", "failed", "skipped")}}
