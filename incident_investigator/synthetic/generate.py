"""Generate 12 distinct incident inputs and separate ground answers, deterministically."""
import csv
import json
from pathlib import Path

from data.make_sample import baseline, change, degrade


def build_dataset():
    cases, answers = [], {}
    for n in range(1, 13):
        world = baseline(100 + n)
        service, category = "payment-service", "bad_config"
        failures = {"seed": 100 + n}
        expected = "root_cause_identified"
        misleading, conflicting, tool_failure = [], [], []
        if n == 1:
            title = "Checkout timeouts following database CPU saturation"
            service, category = "postgres-primary", "resource_exhaustion"
            degrade(world, service, 30, "CPU exhausted; query execution queue saturated")
            degrade(world, "payment-service", 40, "upstream postgres-primary query timeout")
            degrade(world, "checkout-api", 50, "upstream payment-service timeout")
            change(world, "recommendation-service", 55, "Refresh carousel text")
            cause = "Database CPU saturation starts first, causing payment query timeouts and then checkout failures along the dependency path."
            timeline = ["30: database CPU saturation", "40: payment query timeouts", "50: checkout timeouts", "55: unrelated recommendation release"]
            misleading = ["Recommendation deployment occurs after the symptoms and its metrics remain healthy."]
        elif n == 2:
            title = "Checkout submission failures after release"
            service, category = "checkout-api", "bad_deploy"
            change(world, service, 40, "Replace checkout request parser")
            degrade(world, service, 45, "request parser exception on valid checkout payload")
            cause = "Checkout parser regression introduced by the release; dependencies remain healthy."
            timeline = ["40: checkout parser release", "45: checkout failures begin"]
            misleading = ["A dependency warning is isolated and predates the incident."]
            world["logs"].append({"ts": 20, "service": "payment-service", "level": "WARN", "message": "single slow query; recovered"})
        elif n == 3:
            title = "Checkout and payment timeouts with database load"
            service, category = "postgres-primary", "resource_exhaustion"
            degrade(world, service, 35, "CPU exhausted; query execution queue saturated")
            degrade(world, "payment-service", 45, "upstream postgres-primary query timeout")
            degrade(world, "checkout-api", 55, "upstream payment-service timeout")
            change(world, "checkout-api", 60, "Update response header formatting")
            cause = "Database CPU saturation precedes payment and checkout failures along the dependency path."
            timeline = ["35: database saturation", "45: payment timeouts", "55: checkout timeouts", "60: unrelated checkout release"]
            misleading = ["Checkout deployment happened after the first symptoms."]
        elif n == 4:
            title = "Checkout latency with recommendation errors"
            service, category = "redis-cache", "resource_exhaustion"
            degrade(world, service, 35, "memory exhausted; continuous cache eviction storm")
            degrade(world, "recommendation-service", 45, "upstream redis-cache timeout")
            degrade(world, "checkout-api", 55, "upstream recommendation-service timeout")
            world["past_incidents"] = [{"id": "HIST-CACHE", "summary": "checkout latency after payment deployment",
                "tags": ["checkout", "latency"], "root_cause": "payment parser regression", "root_cause_category": "bad_deploy"}]
            cause = "Cache eviction storm degrades recommendations and then checkout, despite a misleading past incident."
            timeline = ["35: cache hit rate collapses", "45: recommendations degrade", "55: checkout degrades"]
            misleading = ["Historical payment deployment explanation has no matching current change."]
        elif n == 5:
            title = "Checkout failures without a recent deployment"
            category = "dependency_failure"
            degrade(world, service, 40, "TLS connection refused by external payment gateway: certificate expired")
            degrade(world, "checkout-api", 50, "upstream payment-service timeout")
            world["metrics"].extend({"ts": t, "service": service, "metric": "cpu_pct", "value": 20} for t in range(0, 105, 5))
            cause = "Payment gateway TLS certificate expiration breaks payment connectivity; normal CPU does not rule this out."
            timeline = ["40: payment TLS failures", "50: checkout failures"]
            conflicting = ["Payment CPU remains normal while connection errors and latency increase; these measure different failure modes."]
        elif n == 6:
            title = "Payment failures despite healthy status probes"
            change(world, service, 40, "Set database endpoint to an unreachable host", "config")
            degrade(world, service, 45, "database connection refused at newly configured host")
            degrade(world, "checkout-api", 55, "upstream payment-service timeout")
            world["logs"].append({"ts": 46, "service": service, "level": "WARN", "message": "health probe HTTP 200; probe checks process only, not database connectivity"})
            cause = "Wrong database endpoint in payment configuration; process liveness is healthy while functional requests fail."
            timeline = ["40: endpoint changed", "45: functional errors", "46: shallow probe reports healthy", "55: checkout fails"]
            conflicting = ["Healthy liveness probe conflicts with request failures because it excludes the database."]
        elif n == 7:
            title = "Checkout timeouts following cache eviction failures"
            service, category = "redis-cache", "resource_exhaustion"
            degrade(world, service, 30, "memory exhausted; continuous cache eviction storm")
            degrade(world, "recommendation-service", 40, "upstream redis-cache timeout")
            degrade(world, "checkout-api", 50, "upstream recommendation-service timeout")
            world["past_incidents"] = [{"id": "HIST-CHECKOUT-007",
                "summary": "checkout latency caused by checkout serialization release",
                "tags": ["checkout", "latency", "timeout"],
                "root_cause": "checkout serialization regression", "root_cause_category": "bad_deploy"}]
            change(world, "payment-service", 60, "Refresh payment response labels")
            cause = "Cache memory exhaustion triggers an eviction storm, degrading recommendations and then checkout; payment remains healthy."
            timeline = ["30: cache hit rate collapses", "40: recommendations degrade", "50: checkout timeouts", "60: unrelated payment release"]
            misleading = ["Historical checkout deployment explanation has no matching current checkout change.",
                          "Payment deployment follows the symptoms and payment metrics remain healthy."]
        elif n == 8:
            title = "Checkout latency following cache memory exhaustion"
            service, category = "redis-cache", "resource_exhaustion"
            degrade(world, service, 40, "memory exhausted; continuous cache eviction storm")
            degrade(world, "recommendation-service", 50, "upstream redis-cache timeout")
            degrade(world, "checkout-api", 60, "upstream recommendation-service timeout")
            world["past_incidents"] = [{"id": "HIST-DB", "summary": "checkout payment timeout from database CPU saturation",
                "tags": ["checkout", "payment", "timeout"], "root_cause": "database saturation", "root_cause_category": "resource_exhaustion"}]
            change(world, "checkout-api", 65, "Refresh checkout response labels")
            cause = "Cache memory exhaustion causes sustained evictions and a falling hit rate, degrading recommendations and then checkout; database and payment metrics remain healthy."
            timeline = ["40: cache hit rate collapses", "50: recommendations degrade", "60: checkout timeouts", "65: unrelated checkout release"]
            misleading = ["Keyword-matching historical database incident contradicts healthy current database measurements.",
                          "Checkout deployment occurs after the symptoms and cannot explain their onset."]
        elif n == 9:
            category = "bad_deploy"
            title = "Checkout failures with unreliable telemetry"
            change(world, service, 40, "Release payment handler that exhausts the connection pool")
            degrade(world, service, 45, "database connection pool exhausted after handler release")
            degrade(world, "checkout-api", 55, "upstream payment-service timeout")
            timeline = ["40: payment handler release", "45: payment degradation", "55: checkout degradation"]
            cause = "Payment handler release exhausts the connection pool, preceding downstream checkout degradation."
            failures.update(timeout_p=.25)
            tool_failure = ["Seeded transient timeouts can affect any query; successful retries provide evidence."]
        elif n == 10:
            title = "Checkout timeouts during database saturation with unavailable logs"
            service, category = "postgres-primary", "resource_exhaustion"
            degrade(world, service, 30, "CPU exhausted; query execution queue saturated")
            degrade(world, "payment-service", 40, "upstream postgres-primary query timeout")
            degrade(world, "checkout-api", 50, "upstream payment-service timeout")
            change(world, "recommendation-service", 55, "Refresh carousel text")
            failures.update(always_fail=["query_logs"], partial_p=.25)
            cause = "Database CPU saturation starts first, causing payment query timeouts and then checkout failures along the dependency path, as in SYN-001. Logs are unavailable, so use metric onset timing and topology and preserve uncertainty from truncated results."
            timeline = ["30: database CPU saturation", "40: payment query timeouts", "50: checkout timeouts", "55: unrelated recommendation release"]
            misleading = ["Recommendation deployment occurs after the symptoms and its metrics remain healthy."]
            tool_failure = ["Log queries always time out; some other tool responses are truncated."]
        elif n == 11:
            title = "Checkout outage with contradictory upstream probes"
            service, category, expected = None, "unknown", "inconclusive"
            world["metrics"] = [row for row in world["metrics"] if row["service"] == "checkout-api"]
            degrade(world, "checkout-api", 55, "upstream request failed; target not recorded")
            for svc in ("payment-service", "recommendation-service"):
                world["logs"].extend([
                    {"ts": 50, "service": svc, "level": "ERROR", "message": "probe A reports service unavailable"},
                    {"ts": 50, "service": svc, "level": "WARN", "message": "probe B reports service healthy; probe scope and clock alignment unavailable"}])
            cause = "No unique root cause is specified by this observable world; conflicting upstream probes cannot distinguish the candidates."
            timeline = ["50: contradictory probes for both upstream services", "55: checkout failures"]
            conflicting = ["Same-time healthy and unhealthy probes for both candidates, without scope or timing validation."]
        else:
            title = "Checkout outage during a monitoring access failure"
            change(world, service, 40, "Point payment database endpoint to an unreachable host", "config")
            degrade(world, service, 45, "database connection refused")
            degrade(world, "checkout-api", 55, "upstream payment-service timeout")
            failures["always_fail"] = ["query_logs", "query_metrics", "get_deployments", "get_dependencies", "search_past_incidents"]
            expected = "inconclusive"
            cause = "Hidden causal event is a bad payment database endpoint; all tools fail, so an agent must not claim it has established this cause."
            timeline = ["40: hidden endpoint change", "45: hidden payment errors", "55: hidden checkout errors"]
            tool_failure = ["All investigation tools always time out; no supporting evidence can be retrieved."]

        incident_id = f"SYN-{n:03d}"
        cases.append({"incident": {"id": incident_id, "title": title, "reported_at": 100,
            "affected_service": "checkout-api", "description": "Customers report slow or failed checkout requests. Investigate the available evidence."},
            "world": world, "failures": failures})
        answers[incident_id] = {"service": service, "category": category, "expected_outcome": expected,
            "root_cause": cause, "causal_timeline": timeline,
            "misleading_evidence": misleading, "conflicting_observations": conflicting,
            "tool_failures": tool_failure,
            "expected_investigation": "Compare causal timing and dependency paths; cite retrieved observations; distinguish assumptions and gaps.",
            "recommended_actions": ["Restore telemetry and escalate for missing evidence"] if expected == "inconclusive" else
                ["Validate the causal mechanism with the owning service team", "Revert the identified change or mitigate the identified dependency/resource failure", "Verify error and latency recovery"]}
    return cases, answers


def main():
    root = Path(__file__).resolve().parent
    (root / "incidents").mkdir(parents=True, exist_ok=True)
    cases, answers = build_dataset()
    for number, case in enumerate(cases, 1):
        (root / "incidents" / f"inc_{number:03d}.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    (root / "ground_truth.json").write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
    with (root / "ground_answers.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["incident_id", "service", "category", "expected_outcome", "root_cause"])
        writer.writeheader()
        writer.writerows({"incident_id": key, **{field: answer[field] for field in writer.fieldnames[1:]}} for key, answer in answers.items())
    lines = ["# Evaluator ground answers", "", "Keep this file out of agent inputs.", ""]
    for key, answer in answers.items():
        lines += [f"## {key}", "", f"Expected outcome: {answer['expected_outcome']}", "",
            f"Service: {answer['service']}; category: {answer['category']}", "", answer["root_cause"], "",
            "Timeline: " + "; ".join(answer["causal_timeline"]), "",
            "Challenges: " + "; ".join(answer["misleading_evidence"] + answer["conflicting_observations"] + answer["tool_failures"]), ""]
    (root / "GROUND_ANSWERS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {len(cases)} incidents and separate ground answers in {root}")


if __name__ == "__main__":
    main()
