"""LLM wrapper: one interface, token/latency accounting, JSON-only outputs."""
from __future__ import annotations
import json, os, re, time
from dataclasses import dataclass


@dataclass
class LLMStats:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency: float = 0.0


SCHEMAS = {
 "orchestrator": 'You plan an incident investigation. Return {"tasks":[{"key":str,"agent":"observability|dependency",'
   '"kind":"scan_logs|scan_metrics|topology|changes|past_incidents","params":{...},"depends_on":[key,...]}]}. '
   'Use params {"services":[..]|"neighbors_of":svc,"start":int,"end":int} for observability, {"service":..} for topology, '
   '{"start","end"} for changes, {"keywords":[..]} for past_incidents. Tasks needing topology must depend on it.',
 "observability": 'You interpret raw log/metric tool output. Report only what the data shows. Return {"findings":[{"content":str,'
   '"kind":"fact|assumption","category":"onset|stable|error_log","service":str,"ts":int|null,"meta":{}}]}. '
   'onset = first sustained deviation from baseline (ignore single-point blips). Mention truncated data as a limitation.',
 "dependency": 'You interpret deployment, topology and past-incident tool output. Return {"findings":[{"content":str,'
   '"kind":"fact|assumption","category":"change|topology|past_incident","service":str|null,"ts":int|null,"meta":{}}]}. '
   'Topology meta: {"service","depends_on":[],"depended_on_by":[],"neighbors":[]}. Change meta: {"change_type":"deploy|config",'
   '"version","description"}. Past incidents are analogies, so kind=assumption, meta {"incident_id","root_cause_category","root_cause"}.',
 "reasoning": 'You are a root-cause analyst. From the evidence list build 1-5 competing hypotheses. Cite evidence ids ONLY from the list. '
   'Weigh timing (cause precedes symptom), dependency path, and contradicting evidence; penalise open_gaps. '
   'Return {"hypotheses":[{"statement","category","service","confidence":0-1,"supporting":[ids],"contradicting":[ids],"assumptions":[str]}]}, best first.',
 "critic": 'You are a skeptical reviewer. Attack the top hypothesis: missing timing evidence, unresolved gaps, red herrings, close competitors, '
   'support that is only assumption. Return {"verdict":"approve|challenge","issues":[str],"requests":[{"agent":"observability|dependency",'
   '"kind":"scan_logs|scan_metrics|topology|changes|past_incidents","params":{...},"reason":str}]}. Challenge only if new evidence could change the outcome.',
 "reporting": 'Write the incident report narrative. Never claim more than the evidence supports; if outcome is inconclusive say so and list what is missing. '
   'Return {"summary":str,"recommended_actions":[str]}.',
}


class BaseLLM:
    def __init__(self):
        self.stats = LLMStats()

    async def json(self, role: str, payload: dict) -> dict:
        t = time.perf_counter()
        out, tin, tout = await self._complete(role, payload)
        s = self.stats
        s.calls += 1; s.input_tokens += tin; s.output_tokens += tout; s.latency += time.perf_counter() - t
        return out

    async def _complete(self, role: str, payload: dict) -> tuple[dict, int, int]:
        raise NotImplementedError


class GroqLLM(BaseLLM):
    def __init__(self, model: str | None = None):
        super().__init__()
        from groq import AsyncGroq                         # pip install groq; needs GROQ_API_KEY
        self.client = AsyncGroq()
        self.model = model or os.environ.get("GROQ_MODEL") or os.environ.get("MODEL") or "qwen/qwen3.8-27b"

    async def _complete(self, role, payload):
        tin = tout = 0
        for _ in range(2):                                # one repair attempt on malformed JSON
            r = await self.client.chat.completions.create(
                model=self.model, max_completion_tokens=2500, temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SCHEMAS[role] + " Respond with a single JSON object only, no prose."},
                    {"role": "user", "content": json.dumps(payload)}])
            if r.usage is not None:
                tin += r.usage.prompt_tokens; tout += r.usage.completion_tokens
            text = re.sub(r"^```(?:json)?|```$", "", (r.choices[0].message.content or "").strip(), flags=re.M).strip()
            try:
                out = json.loads(text)
                if not isinstance(out, dict):
                    raise ValueError("Expected a JSON object")
                return out, tin, tout
            except (json.JSONDecodeError, ValueError):
                continue
        raise ValueError(f"{role}: model did not return valid JSON")
