"""One agent chooses a tool or a final answer on every iteration."""
import asyncio
import math
from dataclasses import asdict

from incident_agents.models import FinalReport, Hypothesis, ToolResult
from incident_agents.state import InvestigationState
from incident_agents.tools import ToolTimeout, ToolInputError
from .config import SingleAgentConfig


class InvestigationDeadlineTimeout(asyncio.TimeoutError):
    """The overall investigation budget limited this request."""


class SingleAgentInvestigator:
    def __init__(self, llm, toolbox, cfg=None):
        self.llm, self.toolbox, self.cfg = llm, toolbox, cfg or SingleAgentConfig()

    async def investigate(self, incident):
        state = InvestigationState(incident, self.cfg)
        observations, issues, decision = [], [], {}
        initial = asdict(self.llm.stats)
        reason, steps = "step_limit_reached", 0
        # One initial decision, a bounded number of tool decisions, and a final decision.
        for step in range(self.cfg.max_tool_calls + 2):
            state.round = steps = step
            if state.elapsed() >= self.cfg.wall_clock:
                reason = "wall_clock_timeout"; break
            try:
                decision = await self._decide({
                    "incident": incident, "window": state.window, "observations": observations,
                    "remaining_tool_calls": self.cfg.max_tool_calls - state.tool_calls,
                    "feedback": issues[-5:],
                }, state)
                if not isinstance(decision, dict):
                    raise ValueError("Decision must be a JSON object")
            except asyncio.TimeoutError as exc:
                reason = "wall_clock_timeout" if isinstance(exc, InvestigationDeadlineTimeout) or state.elapsed() >= self.cfg.wall_clock else "llm_timeout"
                limit = getattr(self.cfg, "llm_timeout", self.cfg.task_timeout)
                issues.append(f"Overall investigation deadline reached ({self.cfg.wall_clock:g}s)" if reason == "wall_clock_timeout"
                              else f"LLM decision exceeded {limit:g}s per attempt; bounded retries exhausted")
                break
            except Exception as exc:
                reason = "llm_failed"; issues.append(f"Single-agent decision failed: {type(exc).__name__}"); break
            if decision.get("action") == "final":
                reason = "agent_finished"; break
            if state.tool_calls >= self.cfg.max_tool_calls:
                reason = "tool_budget_exhausted"; break
            if decision.get("action") != "tool":
                issues.append("Return action=tool or action=final"); continue
            tool, args = decision.get("tool"), decision.get("args")
            if tool not in self.toolbox.TOOLS or not isinstance(args, dict):
                issues.append("Invalid tool or arguments; use the documented tool interface"); continue
            result = await self._call(tool, args, state)
            ref = state.add_evidence(task_id=None, source="single_agent", kind="fact",
                category="tool_result", service=args.get("service"),
                content=f"Observation {len(observations) + 1}: {tool} {args}",
                meta={"tool": tool, "args": args, "result": asdict(result)})
            observations.append({"id": ref, "tool": tool, "args": args, "result": asdict(result)})
            state.log(f"{ref}: {tool} -> {result.completeness}")
        report = self._report(decision if reason == "agent_finished" else {}, observations, state, issues, reason)
        usage = self.llm.stats
        report.stats = {"termination_reason": reason, "decision_steps": steps + 1,
            "tool_calls": state.tool_calls, "llm_calls": usage.calls - initial["calls"],
            "input_tokens": usage.input_tokens - initial["input_tokens"],
            "output_tokens": usage.output_tokens - initial["output_tokens"],
            "latency_s": round(state.elapsed(), 3), "ungrounded_citations": state.ungrounded_citations}
        return report, state

    async def _decide(self, payload, state):
        """Retry a timed-out decision without extending the overall deadline."""
        timeout = getattr(self.cfg, "llm_timeout", self.cfg.task_timeout)
        retries = getattr(self.cfg, "max_llm_retries", 0)
        for attempt in range(retries + 1):
            remaining = self.cfg.wall_clock - state.elapsed()
            if remaining <= 0:
                raise InvestigationDeadlineTimeout()
            try:
                return await asyncio.wait_for(self.llm.json("single_agent", payload), min(timeout, remaining))
            except asyncio.TimeoutError as exc:
                state.log(f"LLM attempt {attempt + 1} timed out (limit {min(timeout, remaining):.2f}s)")
                if remaining <= timeout:
                    raise InvestigationDeadlineTimeout() from exc
                if attempt == retries or state.elapsed() >= self.cfg.wall_clock:
                    raise
                await asyncio.sleep(min(self.cfg.backoff_base * 2 ** attempt,
                                        max(0, self.cfg.wall_clock - state.elapsed())))

    async def _call(self, tool, args, state):
        result = ToolResult(tool, False, [], "failed", "Tool budget exhausted", 0)
        for attempt in range(1, self.cfg.max_tool_retries + 2):
            if state.out_of_budget():
                break
            state.tool_calls += 1
            try:
                result = await asyncio.wait_for(self.toolbox.call(tool, args, attempt),
                    min(self.cfg.tool_timeout, self.cfg.wall_clock - state.elapsed()))
                result.attempts = attempt
                state.tool_log.append({"tool": tool, "attempt": attempt, "completeness": result.completeness})
                return result
            except ToolInputError as exc:
                return ToolResult(tool, False, [], "failed", str(exc), attempt)
            except (ToolTimeout, asyncio.TimeoutError) as exc:
                result = ToolResult(tool, False, [], "failed", str(exc) or "timeout", attempt)
                state.tool_log.append({"tool": tool, "attempt": attempt, "completeness": "timeout"})
                if attempt <= self.cfg.max_tool_retries:
                    await asyncio.sleep(min(self.cfg.backoff_base * 2 ** (attempt - 1),
                                            max(0, self.cfg.wall_clock - state.elapsed())))
            except Exception as exc:
                return ToolResult(tool, False, [], "failed", f"{type(exc).__name__}: tool failed", attempt)
        return result

    def _report(self, decision, observations, state, issues, reason):
        valid = state.evidence_ids()
        def items(key):
            value = decision.get(key, [])
            return value if isinstance(value, list) else []

        for row in items("hypotheses")[:5]:
            try:
                if not isinstance(row, dict):
                    raise ValueError("Hypothesis must be an object")
                confidence = float(row["confidence"])
                if not math.isfinite(confidence):
                    raise ValueError("Non-finite confidence")
                citations = {}
                for key in ("supporting", "contradicting"):
                    requested = row.get(key, [])
                    citations[key] = list(dict.fromkeys(ref for ref in requested if ref in valid))
                    state.ungrounded_citations += sum(ref not in valid for ref in requested)
                state.hypotheses.append(Hypothesis(f"H{len(state.hypotheses)+1}", str(row["statement"]),
                    str(row.get("category", "unknown")), row.get("service"), max(0, min(1, confidence)),
                    citations["supporting"], citations["contradicting"], [str(a) for a in row.get("assumptions", [])]))
            except (KeyError, TypeError, ValueError):
                issues.append("Malformed hypothesis excluded from report")
        state.hypotheses.sort(key=lambda h: -h.confidence)
        for n, h in enumerate(state.hypotheses, 1):
            h.id = f"H{n}"
        gaps = [f"{o['id']}: {o['tool']} returned {o['result']['completeness']} data"
                for o in observations if o["result"]["completeness"] != "full"]
        top = state.hypotheses[0] if state.hypotheses else None
        usable = {o["id"] for o in observations if o["result"]["ok"] and o["result"]["data"]
                  and o["tool"] != "search_past_incidents"}
        margin = top and (len(state.hypotheses) < 2 or top.confidence - state.hypotheses[1].confidence >= self.cfg.min_margin)
        conclusive = bool(reason == "agent_finished" and not decision.get("inconclusive", False)
            and top and top.confidence >= self.cfg.confidence_threshold and margin and usable.intersection(top.supporting))
        if not conclusive:
            issues.append("Evidence or hypothesis separation is insufficient for a conclusive result")
        summary = str(decision.get("summary", "Investigation stopped before a final answer; review collected observations."))
        if not conclusive:
            summary = "Inconclusive. " + summary
        return FinalReport("root_cause_identified" if conclusive else "inconclusive", summary,
            state.hypotheses, list(dict.fromkeys(ref for h in state.hypotheses for ref in h.supporting if ref in usable)),
            list(dict.fromkeys(a for h in state.hypotheses for a in h.assumptions)),
            issues + gaps + [str(x) for x in items("open_issues")],
            [str(x) for x in items("recommended_actions")] or ["Review missing evidence with the service owner"], reason)
