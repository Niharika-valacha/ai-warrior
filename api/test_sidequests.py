"""Side quest pipeline checks with fake search + model (no network). Run: .venv/bin/python -m unittest"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CONTENT_DB", str(Path(tempfile.mkdtemp()) / "content.db"))
import content  # noqa: E402
import sidequests  # noqa: E402

VALID = {
    "oneLiner": "Look things up before answering.",
    "story": {"pain": "Stale facts.", "idea": "Search first.", "unlocked": "Fresh answers.", "origin": "A 2020 paper [1]."},
    "beforeAfter": [{"approach": a, "how": "x", "breaks": "y"} for a in ("Fine-tuning", "Paste all", "RAG")],
    "production": [{"title": t, "text": "z [2]"} for t in ("Support", "Search", "Code")],
    "roles": {r: ["a", "b"] for r in ("qa", "frontend", "backend", "leadership")},
    "tools": [{"group": g, "items": [{"name": "n", "what": "w"}]} for g in ("Build it", "Test it")],
    "atScale": {"lead": "Easy demo.", "ops": [{"name": f"op{i}", "text": "t"} for i in range(4)], "modelShare": 15, "takeaway": "Engineering."},
}


def fake_search(query, max_results=5):
    # Every query returns one shared result plus one unique to the query.
    return [{"title": "Shared", "url": "https://shared", "content": "c"}, {"title": query, "url": f"https://{hash(query)}", "content": "c"}]


class SideQuestTest(unittest.TestCase):
    def setUp(self):
        content.DB_PATH.unlink(missing_ok=True)

    def test_research_dedupes_and_numbers_sources(self):
        sources = sidequests.research("RAG", fake_search)
        self.assertEqual(len(sources), 1 + len(sidequests.QUERIES))  # shared result kept once
        self.assertEqual([s["n"] for s in sources], list(range(1, len(sources) + 1)))

    def test_one_failed_search_does_not_sink_the_quest(self):
        def flaky(query, max_results=5):
            if "origin" in query:
                raise sidequests.tavily.SearchUnavailable("timeout")
            return fake_search(query)

        self.assertEqual(len(sidequests.research("RAG", flaky)), len(sidequests.QUERIES))  # shared + 3 unique

    def test_every_search_failing_is_an_honest_error(self):
        def down(query, max_results=5):
            raise sidequests.tavily.SearchUnavailable("timeout")

        with self.assertRaises(sidequests.tavily.SearchUnavailable):
            sidequests.research("RAG", down)

    def test_invalid_json_gets_one_retry_with_the_errors(self):
        calls = []

        def complete(messages, system, schema):
            calls.append(messages)
            return {"json": {"oneLiner": "missing everything"} if len(calls) == 1 else VALID}

        with content.connect() as conn:
            level = content.read_all(conn)["levels"][4]
            result = sidequests.generate(conn, level, fake_search, complete)
        self.assertEqual(len(calls), 2)
        self.assertIn("failed validation", calls[1][-1]["content"])
        self.assertEqual(result["quest"]["atScale"]["modelShare"], 15)

    def test_generated_quest_is_cached(self):
        with content.connect() as conn:
            level = content.read_all(conn)["levels"][4]
            sidequests.generate(conn, level, fake_search, lambda *a, **k: {"json": VALID})
        with content.connect() as conn:
            cached = sidequests.cached(conn, 4)
        self.assertEqual(cached["quest"]["oneLiner"], VALID["oneLiner"])
        self.assertTrue(all("url" in s for s in cached["sources"]))

    def test_model_share_must_be_honest(self):
        bad = {**VALID, "atScale": {**VALID["atScale"], "modelShare": 95}}
        with self.assertRaises(sidequests.ValidationError):
            sidequests.SideQuest.model_validate(bad)


if __name__ == "__main__":
    unittest.main()
