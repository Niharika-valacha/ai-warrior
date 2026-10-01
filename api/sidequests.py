"""Side quests: a deeper, research-backed explainer for each level.

    search the web (Tavily) → Groq writes 6 chapters from those sources only → validate → cache in SQLite

Generated on first open and cached, so every later open is instant. "Ask a follow-up" answers a live
question the same way, without caching. Both refuse to make things up: no keys, no answer.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

import llm
import tavily

# ---------------------------------------------------------------- the shape every side quest must have


class Shape(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Story(Shape):
    pain: str = Field(description="The problem people hit before this existed, in 1-3 sentences")
    idea: str = Field(description="The core idea that fixed it, in 1-3 sentences")
    unlocked: str = Field(description="What became possible because of it, in 1-2 sentences")
    origin: str = Field(description="Where/when it came from, with source numbers like [2]")


class Approach(Shape):
    approach: str
    how: str
    breaks: str = Field(description="Where this approach falls short")


class UseCase(Shape):
    title: str
    text: str = Field(description="1-2 sentences, with source numbers like [4] where they apply")


class Roles(Shape):
    qa: list[str] = Field(min_length=2, max_length=4)
    frontend: list[str] = Field(min_length=2, max_length=4)
    backend: list[str] = Field(min_length=2, max_length=4)
    leadership: list[str] = Field(min_length=2, max_length=4)


class Tool(Shape):
    name: str
    what: str


class ToolGroup(Shape):
    group: str = Field(description='e.g. "Build it", "Test it", "Connect it"')
    items: list[Tool] = Field(min_length=1, max_length=4)


class Op(Shape):
    name: str = Field(description='One or two words, e.g. "Freshness", "Latency"')
    text: str


class AtScale(Shape):
    lead: str = Field(description="One sentence: the demo is easy, running it for real users is the job")
    ops: list[Op] = Field(min_length=4, max_length=6)
    model_share: int = Field(ge=1, le=60, description="Honest % of the production work that is the model itself")
    takeaway: str = Field(description="One sentence on why the rest is software engineering")


class SideQuest(Shape):
    one_liner: str = Field(description="What it is, for a non-engineer, in one sentence")
    story: Story
    before_after: list[Approach] = Field(min_length=3, max_length=4, description="Other approaches, then this concept last")
    production: list[UseCase] = Field(min_length=3, max_length=4)
    roles: Roles
    tools: list[ToolGroup] = Field(min_length=2, max_length=4)
    at_scale: AtScale


# ---------------------------------------------------------------- research


QUERIES = [
    "{name} in LLM engineering: origin, who introduced it and what problem it solved",
    "{name} in production AI applications: how companies use it",
    "{name} for LLM apps: open source tools, libraries and frameworks",
    "{name} for LLM apps at scale: challenges and best practices",
]

Search = Callable[[str], list[dict]]
Complete = Callable[..., dict]


def research(name: str, search: Search = tavily.search) -> list[dict]:
    """Run the queries in parallel and return unique sources, numbered from 1.
    One slow or failed query just contributes nothing; only if every query fails is there nothing to write from."""

    def safe(query: str) -> list[dict]:
        try:
            return search(query.format(name=name))
        except tavily.SearchUnavailable:
            return []

    with ThreadPoolExecutor(max_workers=len(QUERIES)) as pool:
        batches = list(pool.map(safe, QUERIES))
    if not any(batches):
        raise tavily.SearchUnavailable("Every web search failed, so there's nothing to write the side quest from")
    seen, sources = set(), []
    for result in (r for batch in batches for r in batch):
        if result["url"] not in seen:
            seen.add(result["url"])
            sources.append({"n": len(sources) + 1, **result})
    return sources


def numbered(sources: list[dict], chars: int = 700) -> str:
    return "\n\n".join(f"[{s['n']}] {s['title']} ({s['url']})\n{s['content'][:chars]}" for s in sources)


# ---------------------------------------------------------------- writing

WRITER = """You write a "side quest": a deeper explainer for one concept in a live engineering talk.
The room has QA engineers, frontend developers, juniors, interns, the CTO and the CEO.

Rules:
- Plain English. Short sentences. No hype. Explain any term the first time you use it.
- Use only facts the numbered sources support. Cite them with their numbers, like [3], in story.origin and in
  production texts. If the sources don't support a claim, leave it out. Never invent a company, date or number.
- The game's running example is FoodieGo, a food delivery app's AI support agent. Use it in examples where it helps.
- beforeAfter: 2-3 other ways people tried to solve the same problem, then this concept as the last row.
- roles: what this concept means for each person's daily job, as short actionable bullets.
- atScale.modelShare: your honest estimate, as a percent, of how much of running this in production is the model itself
  versus everything engineered around it.

Concept from the game: {concept}"""


def write(level: dict, sources: list[dict], complete: Complete = llm.generate) -> SideQuest:
    """Ask the model for a side quest; validate it; retry once with the validation errors."""
    system = WRITER.format(concept=json.dumps(level["concept"], ensure_ascii=False))
    messages = [{"role": "user", "content": f"Concept: {level['concept']['name']}\n\nSources:\n{numbered(sources)}"}]
    schema = SideQuest.model_json_schema(by_alias=True)
    for attempt in range(2):
        reply = complete(messages, system=system, schema=schema)
        try:
            return SideQuest.model_validate(reply["json"])
        except ValidationError as err:
            if attempt:
                raise
            messages += [
                {"role": "assistant", "content": json.dumps(reply["json"])},
                {"role": "user", "content": f"That JSON failed validation, fix it and reply with the full object:\n{err}"},
            ]
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- cache


def cached(conn, level_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM side_quests WHERE level_id = ?", (level_id,)).fetchone()
    if row is None:
        return None
    return {
        "levelId": level_id,
        "quest": json.loads(row["content"]),
        "sources": json.loads(row["sources"]),
        "model": row["model"],
        "generatedAt": row["generated_at"],
    }


def generate(conn, level: dict, search: Search = tavily.search, complete: Complete = llm.generate) -> dict:
    """Research, write, validate and cache the side quest for one level. Overwrites any cached version."""
    sources = research(level["concept"]["name"], search)
    quest = write(level, sources, complete)
    cited = [{"n": s["n"], "title": s["title"], "url": s["url"]} for s in sources]
    conn.execute(
        "INSERT OR REPLACE INTO side_quests (level_id, content, sources, model, generated_at) VALUES (?, ?, ?, ?, ?)",
        (
            level["id"],
            quest.model_dump_json(by_alias=True),
            json.dumps(cited, ensure_ascii=False),
            llm.model_name(),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    return cached(conn, level["id"])  # type: ignore[return-value]


# ---------------------------------------------------------------- live follow-up questions

ANSWERER = """Answer a question asked live by someone in the audience of an engineering talk about {concept}.
Under 120 words. Plain English. Use only the numbered sources and cite them like [2].
If the sources don't answer the question, say that plainly instead of guessing."""


def ask(level: dict, question: str, search: Search = tavily.search, complete: Complete = llm.generate) -> dict:
    name = level["concept"]["name"]
    sources = [{"n": i + 1, **r} for i, r in enumerate(search(f"{question} ({name}, LLM engineering)"))]
    reply = complete(
        [{"role": "user", "content": f"Question: {question}\n\nSources:\n{numbered(sources, chars=900)}"}],
        system=ANSWERER.format(concept=name),
    )
    return {
        "question": question,
        "answer": reply["text"],
        "sources": [{"n": s["n"], "title": s["title"], "url": s["url"]} for s in sources],
        "model": llm.model_name(),
    }
