"""Deterministic stand-in for the LLM so everything runs offline and tests are reproducible.

It implements generic rules (timing, dependency path, keyword categories) over the evidence it is
given. It never sees incident ids or ground truth, so behaviour comes from the data, not the case.
"""
from __future__ import annotations
import json, re, statistics
from .llm import BaseLLM

STOP = {"the", "and", "for", "with", "from", "that", "this", "after", "users", "started", "seeing", "are", "was", "has", "have"}
RESOURCE = ("exhaust", "pool", "oom", "out of memory", "disk full", "saturat", "limit", "queue full")
DEPFAIL = ("timeout", "unreachable", "refused", "unavailable", "5xx")
ACTIONS = {
    "bad_deploy": ["Roll back {s} to the version before the change", "Add canary analysis on {s} latency/error metrics to the release pipeline"],
    "bad_config": ["Revert the configuration change on {s}", "Require review and staged rollout for {s} config changes"],
    "resource_exhaustion": ["Increase capacity or limits on {s}", "Add saturation alerts on {s}"],
    "dependency_failure": ["Fail over or circuit-break calls to {s}", "Engage the owner of {s} and review its health"],
    "service_degradation": ["Inspect {s} logs and recent traffic changes", "Add SLO alerting on {s}"],
}


class MockLLM(BaseLLM):
    async def _complete(self, role, payload):
        out = getattr(self, "_" + role)(payload)
        return out, len(json.dumps(payload)) // 4, len(json.dumps(out)) // 4

    # ---------------- orchestrator ----------------
    def _orchestrator(self, p):
        inc, w = p["incident"], p["window"]
        svc = inc["affected_service"]
        text = (inc["title"] + " " + inc["description"]).lower()
        kws = sorted({t for t in re.findall(r"[a-z]{4,}", text) if t not in STOP})
        win = {"start": w["start"], "end": w["end"]}
        return {"tasks": [
            {"key": "topo", "agent": "dependency", "kind": "topology", "params": {"service": svc}},
            {"key": "chg", "agent": "dependency", "kind": "changes", "params": win},
            {"key": "past", "agent": "dependency", "kind": "past_incidents", "params": {"keywords": kws}},
            {"key": "log", "agent": "observability", "kind": "scan_logs", "params": {"services": [svc], **win}},
            {"key": "met", "agent": "observability", "kind": "scan_metrics", "params": {"services": [svc], **win}},
            {"key": "nlog", "agent": "observability", "kind": "scan_logs", "params": {"neighbors_of": svc, **win}, "depends_on": ["topo"]},
            {"key": "nmet", "agent": "observability", "kind": "scan_metrics", "params": {"neighbors_of": svc, **win}, "depends_on": ["topo"]},
        ]}

    # ---------------- observability ----------------
    def _observability(self, p):
        findings = []
        for res in p["results"]:
            svc, rows = res["service"], res["rows"]
            if p["tool"] == "query_logs":
                groups: dict[str, list] = {}
                for r in rows:
                    if r["level"] == "ERROR":
                        groups.setdefault(re.sub(r"\d+", "#", r["message"]), []).append(r)
                for msg, rs in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:3]:
                    findings.append({"content": f"{svc}: {len(rs)} ERROR logs '{msg}', first at t={rs[0]['ts']}",
                                     "kind": "fact", "category": "error_log", "service": svc, "ts": rs[0]["ts"],
                                     "meta": {"count": len(rs), "message": msg}})
            else:
                by_metric: dict[str, list] = {}
                for r in rows:
                    by_metric.setdefault(r["metric"], []).append(r)
                for metric, rs in by_metric.items():
                    f = self._deviation(svc, metric, sorted(rs, key=lambda r: r["ts"]))
                    if f:
                        findings.append(f)
        return {"findings": findings}

    @staticmethod
    def _deviation(svc, metric, rs):
        if len(rs) < 6:
            return None
        vals = [r["value"] for r in rs]
        base_vals = vals[: max(3, len(vals) // 3)]
        base, sd = statistics.median(base_vals), statistics.pstdev(base_vals)
        thr = max(4 * sd, 0.5 * abs(base), 0.5)
        dev = [abs(v - base) > thr for v in vals]
        for i in range(len(vals) - 1):                       # need 2 consecutive points: ignores one-off blips
            if dev[i] and dev[i + 1]:
                peak = max(vals[i:], key=lambda v: abs(v - base))
                return {"content": f"{svc}.{metric} deviated at t={rs[i]['ts']} (baseline {base:.1f} -> peak {peak:.1f})",
                        "kind": "fact", "category": "onset", "service": svc, "ts": rs[i]["ts"],
                        "meta": {"metric": metric, "baseline": base, "peak": peak}}
        return {"content": f"{svc}.{metric} stable around {base:.1f} (no sustained deviation)",
                "kind": "fact", "category": "stable", "service": svc, "ts": None, "meta": {"metric": metric}}

    # ---------------- dependency ----------------
    def _dependency(self, p):
        kind, res, findings = p["task"]["kind"], p["results"], []
        rows = res[0]["rows"] if res else []
        if kind == "topology":
            svc = p["task"]["params"]["service"]
            dep = [r["service"] for r in rows if r["relation"] == "depends_on"]
            by = [r["service"] for r in rows if r["relation"] == "depended_on_by"]
            if rows:
                findings.append({"content": f"{svc} depends on {dep or 'nothing'}; depended on by {by or 'nothing'}",
                                 "kind": "fact", "category": "topology", "service": svc, "ts": None,
                                 "meta": {"service": svc, "depends_on": dep, "depended_on_by": by, "neighbors": dep + by}})
        elif kind == "changes":
            for r in rows:
                findings.append({"content": f"t={r['ts']}: {r['type']} {r.get('version', '')} on {r['service']}: {r['description']}",
                                 "kind": "fact", "category": "change", "service": r["service"], "ts": r["ts"],
                                 "meta": {"change_type": r["type"], "version": r.get("version"), "description": r["description"]}})
        else:
            for r in rows:
                findings.append({"content": f"Similar past incident {r['id']}: {r['summary']} (root cause: {r['root_cause']})",
                                 "kind": "assumption", "category": "past_incident", "service": None, "ts": None,
                                 "meta": {"incident_id": r["id"], "root_cause": r["root_cause"],
                                          "root_cause_category": r.get("root_cause_category")}})
        return {"findings": findings}

    # ---------------- reasoning ----------------
    def _reasoning(self, p):
        ev, affected = p["evidence"], p["incident"]["affected_service"]
        cat = lambda c: [e for e in ev if e["category"] == c]
        onset: dict[str, list] = {}
        for e in cat("onset"):
            onset.setdefault(e["service"], []).append(e)
        first = {s: min(x["ts"] for x in l) for s, l in onset.items()}
        earliest = min(first.values()) if first else None
        earliest_ids = [e["id"] for l in onset.values() for e in l if e["ts"] == earliest]
        topo = {e["meta"]["service"]: e for e in cat("topology")}
        deps = {s: set(e["meta"]["depends_on"]) for s, e in topo.items()}
        path, todo = {affected}, [affected]
        while todo:
            for d in deps.get(todo.pop(), ()):
                if d not in path:
                    path.add(d); todo.append(d)
        topo_known = affected in topo
        reach = lambda sv: self._closure(sv, deps)
        errs: dict[str, list] = {}
        for e in cat("error_log"):
            errs.setdefault(e["service"], []).append(e)
        stable: dict[str, list] = {}
        for e in cat("stable"):
            stable.setdefault(e["service"], []).append(e)
        pen = min(0.2, 0.05 * len(p["open_gaps"]))
        gap_note = [f"Telemetry gap: {g['tool']} for {g['service']} was {g['completeness']}" for g in p["open_gaps"]]
        cands = []

        for c in cat("change"):
            s, m = c["service"], c["meta"]
            score, sup, con, asm = 0.25, [c["id"]], [], list(gap_note)
            if s in first:
                if first[s] >= c["ts"]:
                    score += 0.25; sup += [e["id"] for e in onset[s]]
                else:
                    score -= 0.3; con += [e["id"] for e in onset[s]]
            elif s in stable:
                score -= 0.2; con += [e["id"] for e in stable[s]]
            if topo_known:
                if s in path:
                    score += 0.2; sup.append(topo[affected]["id"])
                else:
                    score -= 0.15; con.append(topo[affected]["id"])
            else:
                asm.append("Dependency path unverified (topology unavailable)")
            if earliest is not None and c["ts"] > earliest:
                score -= 0.3; con += earliest_ids
            down = [x for sv in onset if sv != s and s in reach(sv) for x in onset[sv] if x["ts"] >= c["ts"]]
            if down:                                               # symptoms appeared downstream, after the change
                score += 0.1; sup += [x["id"] for x in down]
            late = [e for e in errs.get(s, []) if e["ts"] is not None and e["ts"] >= c["ts"]]
            if late:
                score += 0.15; sup += [e["id"] for e in late]
            want = "bad_config" if m["change_type"] == "config" else "bad_deploy"
            for pi in cat("past_incident"):
                if pi["meta"].get("root_cause_category") == want:
                    score += 0.1; sup.append(pi["id"]); asm.append("Past incident analogy assumed relevant")
                    break
            mech = errs[s][0]["meta"]["message"] if errs.get(s) else "no direct error evidence"
            cands.append(self._hyp(f"{m['change_type']} {m.get('version') or ''} on {s} ({m['description']}) caused the incident; symptom: {mech}".replace("  ", " "),
                                   want, s, score - pen, sup, con, asm))

        for s, logs in errs.items():
            fo = first.get(s, min(e["ts"] for e in logs))
            if any(c["service"] == s and c["ts"] <= fo for c in cat("change")):
                continue                                           # a change on s already explains it
            if any(first.get(d, 1e9) < first.get(s, 1e9) for d in deps.get(s, ())):
                continue                                           # a dependency broke first: s is a symptom
            msg = logs[0]["meta"]["message"].lower()
            category = ("resource_exhaustion" if any(k in msg for k in RESOURCE) else
                        "dependency_failure" if any(k in msg for k in DEPFAIL) else "service_degradation")
            score, sup, con = 0.2 + 0.1 * min(2, len(logs)), [e["id"] for e in logs], []
            if first.get(s) == earliest and s in first:
                score += 0.25; sup += [e["id"] for e in onset[s]]
            if s in path:
                score += 0.1
            if s in stable:
                score -= 0.2; con += [e["id"] for e in stable[s]]
            cands.append(self._hyp(f"{s} is degraded: {logs[0]['meta']['message']}", category, s, score - pen, sup, con, list(gap_note)))

        cands.sort(key=lambda h: -h["confidence"])
        for i, h in enumerate(cands[:5], 1):
            h["id"] = f"H{i}"
        return {"hypotheses": cands[:5]}

    @staticmethod
    def _closure(start, deps):
        seen, todo = {start}, [start]
        while todo:
            for d in deps.get(todo.pop(), ()):
                if d not in seen:
                    seen.add(d); todo.append(d)
        return seen

    @staticmethod
    def _hyp(statement, category, service, score, sup, con, asm):
        dedup = lambda xs: list(dict.fromkeys(xs))
        return {"statement": statement, "category": category, "service": service,
                "confidence": round(min(0.95, max(0.02, score)), 2),
                "supporting": dedup(sup), "contradicting": dedup(con), "assumptions": asm}

    # ---------------- critic ----------------
    def _critic(self, p):
        hyps, ev, done, win = p["hypotheses"], p["evidence"], p["tasks_done"], p["window"]
        issues, reqs = [], []
        scanned = {(t["kind"], s) for t in done for s in t["services"]}
        ask = lambda agent, kind, params, why: reqs.append({"agent": agent, "kind": kind, "params": params, "reason": why})

        def need_scans(svc, why):
            for kind in ("scan_metrics", "scan_logs"):
                if (kind, svc) not in scanned:
                    ask("observability", kind, {"services": [svc], **win}, why)

        for g in p["open_gaps"]:
            if g["service"] in (None, "*", p["incident"]["affected_service"]) or (hyps and g["service"] == hyps[0]["service"]):
                issues.append(f"Open evidence gap: {g['tool']} for {g['service']} returned {g['completeness']} data")
                ask(g["agent"], g["kind"], {**g["task_params"], "retry": p["round"]}, "re-query to close evidence gap")
        if not hyps:
            return {"verdict": "challenge" if reqs else "approve", "issues": issues + ["No hypotheses could be formed"], "requests": reqs}
        top = hyps[0]
        if top["service"]:
            if not any(e["category"] == "onset" and e["service"] == top["service"] for e in ev):
                issues.append(f"No metric onset evidence for the top suspect {top['service']}; timing is unverified")
            need_scans(top["service"], f"verify timing and errors on top suspect {top['service']}")
        if len(hyps) > 1 and top["confidence"] - hyps[1]["confidence"] < 0.15:
            issues.append("Top two hypotheses are too close to separate")
            if hyps[1]["service"] and hyps[1]["service"] != top["service"]:
                need_scans(hyps[1]["service"], f"discriminate between rival suspects (rival: {hyps[1]['service']})")
        sup = [e for e in ev if e["id"] in top["supporting"]]
        if sup and all(e["kind"] == "assumption" for e in sup):
            issues.append("Top hypothesis is supported only by assumptions")
        if len(top["contradicting"]) >= len(top["supporting"]):
            issues.append("Contradicting evidence outweighs support for the top hypothesis")
        return {"verdict": "challenge" if reqs else "approve", "issues": issues, "requests": reqs}

    # ---------------- reporting ----------------
    def _reporting(self, p):
        top, out = p["top"], p["outcome"]
        if out == "root_cause_identified":
            s = top["service"] or "the affected service"
            return {"summary": f"Most probable root cause (confidence {top['confidence']:.2f}): {top['statement']}.",
                    "recommended_actions": [a.format(s=s) for a in ACTIONS.get(top["category"], ACTIONS["service_degradation"])]}
        gaps = "; ".join(p["open_issues"]) or "evidence is conflicting or too thin"
        lead = f" Leading candidate (low confidence): {top['statement']}." if top else ""
        return {"summary": f"Inconclusive: {gaps}.{lead}",
                "recommended_actions": ["Collect the missing telemetry listed under open issues",
                                        "Apply only safe mitigations (e.g. scale out) until the cause is confirmed",
                                        "Escalate to the on-call owner of the affected service"]}
