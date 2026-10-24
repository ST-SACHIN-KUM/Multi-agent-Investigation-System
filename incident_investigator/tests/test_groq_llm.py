"""Exercise the provider boundary without an API key or installed Groq SDK."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from incident_agents.llm import GroqLLM
from run_investigation import make_llm


def response(content, prompt=10, completion=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


class GroqLLMTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self, responses):
        create = AsyncMock(side_effect=responses)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        sdk = SimpleNamespace(AsyncGroq=lambda: client)
        with patch.dict("sys.modules", {"groq": sdk}), patch.dict("os.environ", {}, clear=True):
            llm = make_llm("groq")
        return llm, create

    async def test_request_and_usage(self):
        llm, create = self.make_client([response('{"hypotheses": []}')])
        payload = {"evidence": []}
        self.assertEqual(await llm.json("reasoning", payload), {"hypotheses": []})
        args = create.call_args.kwargs
        self.assertEqual(args["model"], "qwen/qwen3.8-27b")
        self.assertEqual(args["response_format"], {"type": "json_object"})
        self.assertEqual(args["messages"][0]["role"], "system")
        self.assertEqual(json.loads(args["messages"][1]["content"]), payload)
        self.assertEqual((llm.stats.calls, llm.stats.input_tokens, llm.stats.output_tokens), (1, 10, 5))

    async def test_retry_counts_tokens_from_both_attempts(self):
        llm, create = self.make_client([response("invalid"), response('{"findings": []}')])
        self.assertEqual(await llm.json("observability", {}), {"findings": []})
        self.assertEqual(create.await_count, 2)
        self.assertEqual((llm.stats.input_tokens, llm.stats.output_tokens), (20, 10))

    async def test_invalid_or_empty_output_has_bounded_attempts(self):
        llm, create = self.make_client([response(None), response("[]")])
        with self.assertRaisesRegex(ValueError, "did not return valid JSON"):
            await llm.json("critic", {})
        self.assertEqual(create.await_count, 2)

    def test_model_override_order(self):
        sdk = SimpleNamespace(AsyncGroq=lambda: None)
        with patch.dict("sys.modules", {"groq": sdk}), patch.dict(
            "os.environ", {"GROQ_MODEL": "groq-model", "MODEL": "legacy-model"}, clear=True
        ):
            self.assertEqual(GroqLLM("explicit-model").model, "explicit-model")
            self.assertEqual(GroqLLM().model, "groq-model")
        with patch.dict("sys.modules", {"groq": sdk}), patch.dict(
            "os.environ", {"MODEL": "legacy-model"}, clear=True
        ):
            self.assertEqual(GroqLLM().model, "legacy-model")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown LLM provider"):
            make_llm("unknown")
