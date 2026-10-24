# Evaluator ground answers

Keep this file out of agent inputs.

## SYN-001

Expected outcome: root_cause_identified

Service: postgres-primary; category: resource_exhaustion

Database CPU saturation starts first, causing payment query timeouts and then checkout failures along the dependency path.

Timeline: 30: database CPU saturation; 40: payment query timeouts; 50: checkout timeouts; 55: unrelated recommendation release

Challenges: Recommendation deployment occurs after the symptoms and its metrics remain healthy.

## SYN-002

Expected outcome: root_cause_identified

Service: checkout-api; category: bad_deploy

Checkout parser regression introduced by the release; dependencies remain healthy.

Timeline: 40: checkout parser release; 45: checkout failures begin

Challenges: A dependency warning is isolated and predates the incident.

## SYN-003

Expected outcome: root_cause_identified

Service: postgres-primary; category: resource_exhaustion

Database CPU saturation precedes payment and checkout failures along the dependency path.

Timeline: 35: database saturation; 45: payment timeouts; 55: checkout timeouts; 60: unrelated checkout release

Challenges: Checkout deployment happened after the first symptoms.

## SYN-004

Expected outcome: root_cause_identified

Service: redis-cache; category: resource_exhaustion

Cache eviction storm degrades recommendations and then checkout, despite a misleading past incident.

Timeline: 35: cache hit rate collapses; 45: recommendations degrade; 55: checkout degrades

Challenges: Historical payment deployment explanation has no matching current change.

## SYN-005

Expected outcome: root_cause_identified

Service: payment-service; category: dependency_failure

Payment gateway TLS certificate expiration breaks payment connectivity; normal CPU does not rule this out.

Timeline: 40: payment TLS failures; 50: checkout failures

Challenges: Payment CPU remains normal while connection errors and latency increase; these measure different failure modes.

## SYN-006

Expected outcome: root_cause_identified

Service: payment-service; category: bad_config

Wrong database endpoint in payment configuration; process liveness is healthy while functional requests fail.

Timeline: 40: endpoint changed; 45: functional errors; 46: shallow probe reports healthy; 55: checkout fails

Challenges: Healthy liveness probe conflicts with request failures because it excludes the database.

## SYN-007

Expected outcome: root_cause_identified

Service: redis-cache; category: resource_exhaustion

Cache memory exhaustion triggers an eviction storm, degrading recommendations and then checkout; payment remains healthy.

Timeline: 30: cache hit rate collapses; 40: recommendations degrade; 50: checkout timeouts; 60: unrelated payment release

Challenges: Historical checkout deployment explanation has no matching current checkout change.; Payment deployment follows the symptoms and payment metrics remain healthy.

## SYN-008

Expected outcome: root_cause_identified

Service: redis-cache; category: resource_exhaustion

Cache memory exhaustion causes sustained evictions and a falling hit rate, degrading recommendations and then checkout; database and payment metrics remain healthy.

Timeline: 40: cache hit rate collapses; 50: recommendations degrade; 60: checkout timeouts; 65: unrelated checkout release

Challenges: Keyword-matching historical database incident contradicts healthy current database measurements.; Checkout deployment occurs after the symptoms and cannot explain their onset.

## SYN-009

Expected outcome: root_cause_identified

Service: payment-service; category: bad_deploy

Payment handler release exhausts the connection pool, preceding downstream checkout degradation.

Timeline: 40: payment handler release; 45: payment degradation; 55: checkout degradation

Challenges: Seeded transient timeouts can affect any query; successful retries provide evidence.

## SYN-010

Expected outcome: root_cause_identified

Service: postgres-primary; category: resource_exhaustion

Database CPU saturation starts first, causing payment query timeouts and then checkout failures along the dependency path, as in SYN-001. Logs are unavailable, so use metric onset timing and topology and preserve uncertainty from truncated results.

Timeline: 30: database CPU saturation; 40: payment query timeouts; 50: checkout timeouts; 55: unrelated recommendation release

Challenges: Recommendation deployment occurs after the symptoms and its metrics remain healthy.; Log queries always time out; some other tool responses are truncated.

## SYN-011

Expected outcome: inconclusive

Service: None; category: unknown

No unique root cause is specified by this observable world; conflicting upstream probes cannot distinguish the candidates.

Timeline: 50: contradictory probes for both upstream services; 55: checkout failures

Challenges: Same-time healthy and unhealthy probes for both candidates, without scope or timing validation.

## SYN-012

Expected outcome: inconclusive

Service: payment-service; category: bad_config

Hidden causal event is a bad payment database endpoint; all tools fail, so an agent must not claim it has established this cause.

Timeline: 40: hidden endpoint change; 45: hidden payment errors; 55: hidden checkout errors

Challenges: All investigation tools always time out; no supporting evidence can be retrieved.
