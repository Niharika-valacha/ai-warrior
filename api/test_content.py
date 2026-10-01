"""Content database checks. Run: .venv/bin/python -m unittest"""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ["CONTENT_DB"] = str(Path(tempfile.mkdtemp()) / "content.db")  # never touch the real DB
import content  # noqa: E402


class ContentTest(unittest.TestCase):
    def setUp(self):
        content.DB_PATH.unlink(missing_ok=True)

    def test_seed_round_trips_exactly(self):
        with content.connect() as conn:
            data = content.read_all(conn)
        seed = json.loads(content.SEED.read_text())
        self.assertEqual([{k: v for k, v in lvl.items() if k != "id"} for lvl in data["levels"]], seed["levels"])
        self.assertEqual(data["skillTree"], seed["skillTree"])
        self.assertEqual(data["sidekicks"], seed["sidekicks"])
        self.assertEqual(data["copy"], seed["copy"])

    def test_every_seeded_screen_copy_matches_its_api_model(self):
        import main  # noqa: E402  (imports FastAPI; fine in tests)

        with content.connect() as conn:
            copy = content.read_all(conn)["copy"]
        self.assertEqual(set(copy), set(main.COPY_MODELS))
        for key, value in copy.items():
            main.COPY_MODELS[key].model_validate(value)

    def test_every_level_has_exactly_one_right_answer(self):
        with content.connect() as conn:
            for lvl in content.read_all(conn)["levels"]:
                self.assertEqual(sum(1 for o in lvl["options"] if o.get("correct")), 1, lvl["block"])

    def test_database_rejects_a_second_right_answer(self):
        with self.assertRaises(sqlite3.IntegrityError), content.connect() as conn:
            conn.execute("UPDATE options SET correct = 1 WHERE level_id = 0")

    def test_moving_the_right_answer_keeps_one(self):
        # The old right answer becomes a wrong one, so it needs a fail script and pun first.
        with self.assertRaises(sqlite3.IntegrityError), content.connect() as conn:
            content.update_option(conn, 0, 0, {"correct": True})
        with content.connect() as conn:
            content.update_option(conn, 0, 3, {"fail": ["> it broke"], "pun": "Nope."})
            content.update_option(conn, 0, 0, {"correct": True})
        with content.connect() as conn:
            options = content.read_all(conn)["levels"][0]["options"]
        self.assertEqual([bool(o.get("correct")) for o in options], [True, False, False, False])

    def test_level_edit_persists_lists(self):
        with content.connect() as conn:
            self.assertTrue(content.update_level(conn, 4, {"question": "New?", "blockLines": ["a", "b"]}))
        with content.connect() as conn:
            lvl = content.read_all(conn)["levels"][4]
        self.assertEqual((lvl["question"], lvl["blockLines"]), ("New?", ["a", "b"]))

    def test_unknown_fields_never_reach_sql(self):
        with self.assertRaises(ValueError), content.connect() as conn:
            content.update_level(conn, 0, {"id = 99; --": "x"})


if __name__ == "__main__":
    unittest.main()
