"""Quiz content (levels, options, skill tree, sidekicks, screen copy) in SQLite: the source of truth the game reads.

Lists inside a level (situation lines, run log, fail script...) are stored as JSON columns.
On first run the database is created from data/content.seed.json; export_snapshots.py writes
edits back to that file so they're tracked in git.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

DATA = Path(__file__).parent / "data"
SEED = DATA / "content.seed.json"
DB_PATH = Path(os.environ.get("CONTENT_DB", DATA / "content.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS levels (
  id          INTEGER PRIMARY KEY,          -- play order, starting at 0
  icon        TEXT NOT NULL,
  alert       TEXT NOT NULL,                -- incident label, e.g. HALLUCINATION_DETECTED
  block       TEXT NOT NULL,                -- name of the block it adds to the system
  block_lines TEXT NOT NULL DEFAULT '[]',   -- JSON list
  situation   TEXT NOT NULL DEFAULT '[]',   -- JSON list
  question    TEXT NOT NULL,
  run         TEXT NOT NULL DEFAULT '[]',   -- JSON list: run log for the right answer
  learn       TEXT NOT NULL,
  concept     TEXT NOT NULL                 -- JSON {name, term, parts, twist, line}
);
CREATE TABLE IF NOT EXISTS options (
  level_id INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
  position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 3),
  text     TEXT NOT NULL,
  correct  INTEGER NOT NULL DEFAULT 0 CHECK (correct IN (0, 1)),
  fail     TEXT,                            -- JSON list, wrong answers only
  pun      TEXT,
  PRIMARY KEY (level_id, position),
  CHECK (correct = 1 OR (fail IS NOT NULL AND pun IS NOT NULL))
);
-- At most one right answer per level; tests check there is at least one.
CREATE UNIQUE INDEX IF NOT EXISTS one_right_answer ON options(level_id) WHERE correct = 1;
CREATE TABLE IF NOT EXISTS skill_topics (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  branch   TEXT NOT NULL,
  name     TEXT NOT NULL,
  unlocked INTEGER NOT NULL DEFAULT 0 CHECK (unlocked IN (0, 1)),
  position INTEGER NOT NULL,                -- order within the branch
  UNIQUE (branch, name)
);
CREATE TABLE IF NOT EXISTS sidekicks (
  id       TEXT PRIMARY KEY,                -- also the image name: web/public/avatars/{id}-{mood}.jpg
  name     TEXT NOT NULL,
  role     TEXT NOT NULL,
  move     TEXT NOT NULL,                   -- catchphrase on a win
  think    TEXT NOT NULL,                   -- line while the room decides
  position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS side_quests (
  level_id     INTEGER PRIMARY KEY REFERENCES levels(id) ON DELETE CASCADE,
  content      TEXT NOT NULL,               -- JSON, validated by sidequests.SideQuest
  sources      TEXT NOT NULL,               -- JSON [{n, title, url}]: what the content cites as [n]
  model        TEXT NOT NULL,
  generated_at TEXT NOT NULL                -- ISO timestamp, UTC
);
CREATE TABLE IF NOT EXISTS copy (
  key   TEXT PRIMARY KEY,                   -- a screen: intro, briefing, reactions, boss, tree, win
  value TEXT NOT NULL                       -- JSON object; supports {name}, {levels} and **bold**
);
"""

LEVEL_JSON_FIELDS = ("block_lines", "situation", "run", "concept")
LEVEL_COLUMNS = {"icon", "alert", "block", "block_lines", "situation", "question", "run", "learn", "concept"}
OPTION_COLUMNS = {"text", "correct", "fail", "pun"}


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection to the content database, created and seeded on first use."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SCHEMA)
        if _seed(conn, json.loads(SEED.read_text())):
            conn.commit()  # the seed must survive even if the caller's work rolls back
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _empty(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0  # table names are constants


def _seed(conn: sqlite3.Connection, seed: dict) -> bool:
    """Fill each empty table from the seed. Tables added later get seeded on the next start."""
    seeded = False
    if _empty(conn, "levels"):
        _seed_levels(conn, seed["levels"])
        seeded = True
    if _empty(conn, "skill_topics"):
        _seed_skill_tree(conn, seed["skillTree"])
        seeded = True
    if _empty(conn, "sidekicks"):
        for pos, s in enumerate(seed["sidekicks"]):
            conn.execute(
                "INSERT INTO sidekicks (id, name, role, move, think, position) VALUES (?, ?, ?, ?, ?, ?)",
                (s["id"], s["name"], s["role"], s["move"], s["think"], pos),
            )
        seeded = True
    for key, value in seed["copy"].items():  # per key, so screens added later appear without a reset
        cur = conn.execute(
            "INSERT OR IGNORE INTO copy (key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False))
        )
        seeded = seeded or cur.rowcount == 1
    return seeded


def _seed_levels(conn: sqlite3.Connection, levels: list) -> None:
    for i, lvl in enumerate(levels):
        conn.execute(
            "INSERT INTO levels (id, icon, alert, block, block_lines, situation, question, run, learn, concept)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i, lvl["icon"], lvl["alert"], lvl["block"], json.dumps(lvl["blockLines"], ensure_ascii=False),
             json.dumps(lvl["situation"], ensure_ascii=False), lvl["question"], json.dumps(lvl["run"], ensure_ascii=False),
             lvl["learn"], json.dumps(lvl["concept"], ensure_ascii=False)),
        )
        for pos, opt in enumerate(lvl["options"]):
            conn.execute(
                "INSERT INTO options (level_id, position, text, correct, fail, pun) VALUES (?, ?, ?, ?, ?, ?)",
                (i, pos, opt["text"], int(bool(opt.get("correct"))),
                 json.dumps(opt["fail"], ensure_ascii=False) if "fail" in opt else None, opt.get("pun")),
            )


def _seed_skill_tree(conn: sqlite3.Connection, tree: list) -> None:
    for branch in tree:
        topics = [(t, 1) for t in branch["unlocked"]] + [(t, 0) for t in branch["locked"]]
        for pos, (name, unlocked) in enumerate(topics):
            conn.execute(
                "INSERT INTO skill_topics (branch, name, unlocked, position) VALUES (?, ?, ?, ?)",
                (branch["name"], name, unlocked, pos),
            )


# ---------------------------------------------------------------- reads (shape matches the web app's types)


def read_all(conn: sqlite3.Connection) -> dict:
    options: dict[int, list] = {}
    for o in conn.execute("SELECT * FROM options ORDER BY level_id, position"):
        opt: dict[str, Any] = {"text": o["text"]}
        if o["correct"]:
            opt["correct"] = True
        else:
            opt["fail"], opt["pun"] = json.loads(o["fail"]), o["pun"]
        options.setdefault(o["level_id"], []).append(opt)

    levels = [
        {
            "id": r["id"],
            "icon": r["icon"],
            "alert": r["alert"],
            "block": r["block"],
            "blockLines": json.loads(r["block_lines"]),
            "situation": json.loads(r["situation"]),
            "question": r["question"],
            "options": options.get(r["id"], []),
            "run": json.loads(r["run"]),
            "learn": r["learn"],
            "concept": json.loads(r["concept"]),
        }
        for r in conn.execute("SELECT * FROM levels ORDER BY id")
    ]

    branches: dict[str, dict] = {}
    for t in conn.execute("SELECT * FROM skill_topics ORDER BY (SELECT MIN(id) FROM skill_topics s WHERE s.branch = skill_topics.branch), position"):
        b = branches.setdefault(t["branch"], {"name": t["branch"], "unlocked": [], "locked": []})
        b["unlocked" if t["unlocked"] else "locked"].append(t["name"])
    sidekicks = [
        {k: r[k] for k in ("id", "name", "role", "move", "think")}
        for r in conn.execute("SELECT * FROM sidekicks ORDER BY position")
    ]
    copy = {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM copy")}
    return {"levels": levels, "skillTree": list(branches.values()), "sidekicks": sidekicks, "copy": copy}


def topics(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT id, branch, name, unlocked, position FROM skill_topics ORDER BY id")]


# ---------------------------------------------------------------- writes


def update_level(conn: sqlite3.Connection, level_id: int, changes: dict) -> bool:
    """Partial update. List/object fields are given as Python values and stored as JSON."""
    columns = {"blockLines": "block_lines"}
    sets, args = [], []
    for key, value in changes.items():
        column = columns.get(key, key)
        if column not in LEVEL_COLUMNS:  # column names go into SQL, so only known ones
            raise ValueError(f"unknown level field {key}")
        sets.append(f"{column} = ?")
        args.append(json.dumps(value, ensure_ascii=False) if column in LEVEL_JSON_FIELDS else value)
    if not sets:
        return True
    cur = conn.execute(f"UPDATE levels SET {', '.join(sets)} WHERE id = ?", (*args, level_id))
    return cur.rowcount == 1


def update_option(conn: sqlite3.Connection, level_id: int, position: int, changes: dict) -> bool:
    """Partial update. Making an option correct demotes the old right answer in the same transaction,
    which the database only allows once that old answer has a fail script and a pun."""
    if changes.get("correct"):
        conn.execute("UPDATE options SET correct = 0 WHERE level_id = ? AND correct = 1", (level_id,))
    sets, args = [], []
    for key, value in changes.items():
        if key not in OPTION_COLUMNS:  # column names go into SQL, so only known ones
            raise ValueError(f"unknown option field {key}")
        sets.append(f"{key} = ?")
        args.append(json.dumps(value, ensure_ascii=False) if key == "fail" else int(value) if key == "correct" else value)
    if not sets:
        return True
    cur = conn.execute(
        f"UPDATE options SET {', '.join(sets)} WHERE level_id = ? AND position = ?", (*args, level_id, position)
    )
    return cur.rowcount == 1


def add_topic(conn: sqlite3.Connection, branch: str, name: str, unlocked: bool) -> int:
    position = conn.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM skill_topics WHERE branch = ?", (branch,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO skill_topics (branch, name, unlocked, position) VALUES (?, ?, ?, ?)", (branch, name, int(unlocked), position)
    )
    return cur.lastrowid


def set_topic_unlocked(conn: sqlite3.Connection, topic_id: int, unlocked: bool) -> bool:
    return conn.execute("UPDATE skill_topics SET unlocked = ? WHERE id = ?", (int(unlocked), topic_id)).rowcount == 1


def delete_topic(conn: sqlite3.Connection, topic_id: int) -> bool:
    return conn.execute("DELETE FROM skill_topics WHERE id = ?", (topic_id,)).rowcount == 1


SIDEKICK_COLUMNS = {"name", "role", "move", "think"}


def update_sidekick(conn: sqlite3.Connection, sidekick_id: str, changes: dict) -> bool:
    for key in changes:
        if key not in SIDEKICK_COLUMNS:  # column names go into SQL, so only known ones
            raise ValueError(f"unknown sidekick field {key}")
    if not changes:
        return True
    sets = ", ".join(f"{k} = ?" for k in changes)
    return conn.execute(f"UPDATE sidekicks SET {sets} WHERE id = ?", (*changes.values(), sidekick_id)).rowcount == 1


def set_copy(conn: sqlite3.Connection, key: str, value: dict) -> bool:
    """Replace one screen's copy. The API validates its shape first."""
    cur = conn.execute("UPDATE copy SET value = ? WHERE key = ?", (json.dumps(value, ensure_ascii=False), key))
    return cur.rowcount == 1


def export_seed(data: Optional[dict] = None) -> None:
    """Write the current content back to the seed file, so edits are tracked in git."""
    if data is None:
        with connect() as conn:
            data = read_all(conn)
    seed = {
        "levels": [{k: v for k, v in lvl.items() if k != "id"} for lvl in data["levels"]],
        "skillTree": data["skillTree"],
        "sidekicks": data["sidekicks"],
        "copy": data["copy"],
    }
    SEED.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n")
