"""Provider chain checks with a fake network call. Run: .venv/bin/python -m unittest"""
import os
import unittest
import urllib.error
from unittest import mock

import llm


def http_error(code):
    return urllib.error.HTTPError("https://example", code, "error", {}, None)


class ProviderChainTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"GROQ_API_KEY": "g", "GEMINI_API_KEY": "m", "LLM_PROVIDERS": "groq,gemini"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_call(self, failing: set):
        def call(provider, *args, **kwargs):
            if provider.name in failing:
                raise http_error(429)
            return {"text": f"hi from {provider.name}"}

        return mock.patch.object(llm, "_call", side_effect=call)

    def test_first_provider_answers(self):
        with self.fake_call(failing=set()):
            reply = llm.generate([{"role": "user", "content": "q"}], system="s")
        self.assertEqual(reply["text"], "hi from groq")
        self.assertTrue(reply["model"].startswith("groq/"))

    def test_rate_limited_provider_falls_through_to_the_next(self):
        with self.fake_call(failing={"groq"}):
            reply = llm.generate([{"role": "user", "content": "q"}], system="s")
        self.assertEqual(reply["text"], "hi from gemini")

    def test_generate_raises_when_every_provider_fails(self):
        with self.fake_call(failing={"groq", "gemini"}), self.assertRaises(llm.LLMUnavailable) as ctx:
            llm.generate([{"role": "user", "content": "q"}], system="s")
        self.assertIn("groq HTTP 429 (rate limited)", str(ctx.exception))

    def test_complete_falls_back_to_replay_and_says_why(self):
        with self.fake_call(failing={"groq", "gemini"}), llm.session(live=True):
            reply = llm.complete([{"role": "user", "content": "my order is late"}])
            used = llm.models_used()
        self.assertEqual(reply["model"], "replay")
        self.assertTrue(used[0].startswith("replay (All providers failed"))

    def test_providers_without_a_key_are_skipped(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            self.assertEqual([p.name for p in llm.chain()], ["gemini"])


if __name__ == "__main__":
    unittest.main()
