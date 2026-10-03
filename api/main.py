"""FoodieGo AI Warrior API. Run: .venv/bin/uvicorn main:app --port 8400 --env-file .env

Edit quiz content at http://localhost:8400/docs (writes need the X-Admin-Token header).
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

import content
import demos
import llm
import sidequests
import tavily
from ratelimit import RateLimit

app = FastAPI(title="AI Warrior API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("WEB_ORIGINS", "http://localhost:4000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# Limits per client IP on endpoints that call paid or rate-limited services.
XRAY_LIMIT = RateLimit(limit=20, window_s=60)  # live levels make several model calls each
GENERATE_LIMIT = RateLimit(limit=3, window_s=60)  # writing a side quest: 4 web searches + a long model call
ASK_LIMIT = RateLimit(limit=10, window_s=60)  # a web search + a model call


def require_admin(x_admin_token: str = Header(default="")) -> None:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Send the X-Admin-Token header (ADMIN_TOKEN in api/.env)")


# ---------------------------------------------------------------- game


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/content")
def get_content() -> dict:
    """Everything the game shows: levels with their options, and the skill tree."""
    with content.connect() as conn:
        return content.read_all(conn)


@app.get("/xray/{level}", dependencies=[Depends(XRAY_LIMIT)])
def xray(level: int) -> dict:
    """Run the real code behind a level and return its output, trace and source."""
    if not 0 <= level < len(demos.DEMOS):
        raise HTTPException(status_code=404, detail=f"No level {level}")
    return demos.run(level)


# ---------------------------------------------------------------- content editing (admin)


class Concept(BaseModel):
    name: str
    term: str
    parts: str
    twist: str
    line: str


class LevelPatch(BaseModel):
    icon: Optional[str] = None
    alert: Optional[str] = None
    block: Optional[str] = None
    blockLines: Optional[list[str]] = None
    situation: Optional[list[str]] = None
    question: Optional[str] = None
    run: Optional[list[str]] = None
    learn: Optional[str] = None
    concept: Optional[Concept] = None


class OptionPatch(BaseModel):
    text: Optional[str] = None
    correct: Optional[bool] = None
    fail: Optional[list[str]] = None
    pun: Optional[str] = None


class TopicIn(BaseModel):
    branch: str
    name: str
    unlocked: bool = False


class TopicPatch(BaseModel):
    unlocked: bool


class SidekickPatch(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    move: Optional[str] = None
    think: Optional[str] = None


# Screen copy. Text may use {name}, {levels} and **bold**.
class IntroCopy(BaseModel):
    title: str
    lede: str
    start: str


class BriefingCopy(BaseModel):
    title: str
    incidentId: int
    alert: str
    problem: str
    quotes: list[str]
    job: str
    rules: list[str]
    start: str


class ReactionsCopy(BaseModel):
    fail: str
    retry: str
    shipped: str


class BossCopy(BaseModel):
    taunts: list[str]
    decoy: str  # the button that runs away
    answer: str


class TreeCopy(BaseModel):
    title: str
    lede: str  # also supports {unlocked} and {locked}
    footer: str


class WinCopy(BaseModel):
    title: str
    lede: str
    again: str


class BuiltWith(BaseModel):
    name: str
    what: str


class SideQuestCopy(BaseModel):
    button: str
    loading: str
    askPlaceholder: str
    builtWithTitle: str
    builtWith: list[BuiltWith]


COPY_MODELS: dict[str, type[BaseModel]] = {
    "sidequest": SideQuestCopy,
    "intro": IntroCopy,
    "briefing": BriefingCopy,
    "reactions": ReactionsCopy,
    "boss": BossCopy,
    "tree": TreeCopy,
    "win": WinCopy,
}


def _write(fn, *args) -> None:
    """Run a write; turn "not found" and constraint violations into clean HTTP errors."""
    try:
        with content.connect() as conn:
            if not fn(conn, *args):
                raise HTTPException(status_code=404, detail="Not found")
    except sqlite3.IntegrityError as err:
        raise HTTPException(status_code=409, detail=f"Rejected by the database: {err}") from err


@app.patch("/levels/{level_id}", dependencies=[Depends(require_admin)])
def patch_level(level_id: int, patch: LevelPatch) -> dict:
    _write(content.update_level, level_id, patch.model_dump(exclude_unset=True))
    return {"ok": True}


@app.patch("/levels/{level_id}/options/{position}", dependencies=[Depends(require_admin)])
def patch_option(level_id: int, position: int, patch: OptionPatch) -> dict:
    _write(content.update_option, level_id, position, patch.model_dump(exclude_unset=True))
    return {"ok": True}


@app.get("/skill-topics")
def list_topics() -> list[dict]:
    """Topics with their ids, for editing."""
    with content.connect() as conn:
        return content.topics(conn)


@app.post("/skill-topics", dependencies=[Depends(require_admin)])
def create_topic(topic: TopicIn) -> dict:
    try:
        with content.connect() as conn:
            return {"id": content.add_topic(conn, topic.branch, topic.name, topic.unlocked)}
    except sqlite3.IntegrityError as err:
        raise HTTPException(status_code=409, detail=f"Rejected by the database: {err}") from err


@app.patch("/skill-topics/{topic_id}", dependencies=[Depends(require_admin)])
def patch_topic(topic_id: int, patch: TopicPatch) -> dict:
    _write(content.set_topic_unlocked, topic_id, patch.unlocked)
    return {"ok": True}


@app.delete("/skill-topics/{topic_id}", dependencies=[Depends(require_admin)])
def remove_topic(topic_id: int) -> dict:
    _write(content.delete_topic, topic_id)
    return {"ok": True}


@app.patch("/sidekicks/{sidekick_id}", dependencies=[Depends(require_admin)])
def patch_sidekick(sidekick_id: str, patch: SidekickPatch) -> dict:
    _write(content.update_sidekick, sidekick_id, patch.model_dump(exclude_unset=True))
    return {"ok": True}


@app.put("/copy/{key}", dependencies=[Depends(require_admin)])
def put_copy(key: str, value: dict) -> dict:
    """Replace one screen's text. GET /content shows the current value to start from."""
    model = COPY_MODELS.get(key)
    if model is None:
        raise HTTPException(status_code=404, detail=f"No screen copy called {key}. Try: {', '.join(COPY_MODELS)}")
    try:
        validated = model.model_validate(value).model_dump()
    except ValidationError as err:
        raise HTTPException(status_code=422, detail=err.errors()) from err
    _write(content.set_copy, key, validated)
    return {"ok": True}


# ---------------------------------------------------------------- side quests


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=300)


REFRESH_COOLDOWN_S = 30  # each refresh costs several web searches and a long model call
_last_refresh: dict[int, float] = {}


def _level(conn: sqlite3.Connection, level_id: int) -> dict:
    levels = content.read_all(conn)["levels"]
    if not 0 <= level_id < len(levels):
        raise HTTPException(status_code=404, detail=f"No level {level_id}")
    return levels[level_id]


def _ai_call(fn, *args):
    """Run research + writing; turn missing keys or outages into an honest 503."""
    try:
        return fn(*args)
    except (tavily.SearchUnavailable, llm.LLMUnavailable) as err:
        raise HTTPException(status_code=503, detail=str(err)) from err
    except ValidationError as err:
        raise HTTPException(status_code=502, detail="The model's side quest failed validation twice") from err


@app.get("/side-quests/{level_id}")
def get_side_quest(level_id: int, request: Request) -> dict:
    """Cached side quest, or research and write it now (first open takes ~10-20s)."""
    with content.connect() as conn:
        level = _level(conn, level_id)
        quest = sidequests.cached(conn, level_id)
        if quest:
            return quest  # cached reads are free, so they're not rate-limited
        GENERATE_LIMIT(request)
        return _ai_call(sidequests.generate, conn, level)


@app.post("/side-quests/{level_id}/refresh", dependencies=[Depends(GENERATE_LIMIT)])
def refresh_side_quest(level_id: int) -> dict:
    """Throw away the cached side quest and research it again."""
    wait = REFRESH_COOLDOWN_S - (time.monotonic() - _last_refresh.get(level_id, float("-inf")))
    if wait > 0:
        raise HTTPException(status_code=429, detail=f"Just refreshed. Try again in {wait:.0f}s.")
    _last_refresh[level_id] = time.monotonic()
    with content.connect() as conn:
        return _ai_call(sidequests.generate, conn, _level(conn, level_id))


@app.post("/side-quests/{level_id}/ask", dependencies=[Depends(ASK_LIMIT)])
def ask_follow_up(level_id: int, body: Question) -> dict:
    """Answer a live audience question from fresh web results. Not cached: every question is new."""
    with content.connect() as conn:
        level = _level(conn, level_id)
    return _ai_call(sidequests.ask, level, body.question.strip())
