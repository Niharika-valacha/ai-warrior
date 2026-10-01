"""The one place the system talks to a language model.

complete() returns one of:
  {"text": str}                                   a normal reply
  {"json": dict}                                  when `schema` is given
  {"tool_call": {"name": str, "args": dict}}      when the model wants a tool

It calls Groq when live mode is on and a key is configured. If Groq is slow, down or returns
something unusable, it falls back to the replay model, so a demo never breaks on stage.
That fallback is the same pattern production systems use when a model provider has an outage.
"""
from __future__ import annotations

import contextvars
import json
import os
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Optional

import replay

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"  # override with GROQ_MODEL in .env
TIMEOUT_S = 12

_live = contextvars.ContextVar("live", default=False)
_used: contextvars.ContextVar[Optional[set]] = contextvars.ContextVar("used", default=None)


@contextmanager
def session(live: bool):
    """Choose live or replay for one run, and record which model actually answered."""
    live_token, used_token = _live.set(live), _used.set(set())
    try:
        yield
    finally:
        _live.reset(live_token)
        _used.reset(used_token)


def models_used() -> list[str]:
    return sorted(_used.get() or [])


def complete(
    messages: list[dict],
    system: Optional[str] = None,
    schema: Optional[dict] = None,
    tools: Optional[list[dict]] = None,
) -> dict:
    if _live.get() and os.environ.get("LLM_PROVIDER") == "groq" and os.environ.get("GROQ_API_KEY"):
        try:
            reply = _groq(messages, system, schema, tools)
            _record(os.environ.get("GROQ_MODEL", DEFAULT_MODEL))
            return reply
        except Exception as err:  # timeout, HTTP error, bad JSON: fall back rather than fail
            _record(f"replay (Groq failed: {type(err).__name__})")
            return replay.respond(messages, system=system, schema=schema, tools=tools)
    _record("replay")
    return replay.respond(messages, system=system, schema=schema, tools=tools)


class LLMUnavailable(RuntimeError):
    pass


def generate(messages: list[dict], system: str, schema: Optional[dict] = None, timeout: int = 45) -> dict:
    """A real Groq call with NO replay fallback, for content where a stand-in answer would be wrong
    (side quests, live follow-ups). Raises LLMUnavailable so callers can show an honest error."""
    if not os.environ.get("GROQ_API_KEY"):
        raise LLMUnavailable("GROQ_API_KEY is not set in api/.env")
    try:
        return _groq(messages, system, schema, None, timeout=timeout)
    except urllib.error.HTTPError as err:
        hint = " (rate limit: wait a minute and try again)" if err.code == 429 else ""
        raise LLMUnavailable(f"Groq returned HTTP {err.code}{hint}") from err
    except Exception as err:
        raise LLMUnavailable(f"Groq call failed: {type(err).__name__}") from err


def model_name() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL)


def _record(model: str) -> None:
    used = _used.get()
    if used is not None:
        used.add(model)


# ---------------------------------------------------------------- Groq (OpenAI-compatible API)


def _groq(
    messages: list[dict], system: Optional[str], schema: Optional[dict], tools: Optional[list[dict]], timeout: int = TIMEOUT_S
) -> dict:
    if schema:
        system = f"{system or ''}\nReply with only a JSON object matching this JSON Schema:\n{json.dumps(schema)}"
    body: dict = {
        "model": os.environ.get("GROQ_MODEL", DEFAULT_MODEL),
        "messages": ([{"role": "system", "content": system}] if system else []) + _to_openai(messages),
        "reasoning_effort": "low",
    }
    if schema:
        body["response_format"] = {"type": "json_object"}
    if tools:
        body["tools"] = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
            for t in tools
        ]

    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
            "Content-Type": "application/json",
            "User-Agent": "ai-warrior/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as res:
        message = json.load(res)["choices"][0]["message"]

    if message.get("tool_calls"):
        fn = message["tool_calls"][0]["function"]
        return {"tool_call": {"name": fn["name"], "args": json.loads(fn["arguments"] or "{}")}}
    content = message.get("content") or ""
    return {"json": json.loads(content)} if schema else {"text": content.strip()}


def _to_openai(messages: list[dict]) -> list[dict]:
    """Our message format → OpenAI's. Tool calls and their results are linked by an id."""
    out, call_id = [], None
    for i, m in enumerate(messages):
        if m["role"] == "assistant" and "tool_call" in m:
            call_id = f"call_{i}"
            call = m["tool_call"]
            out.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": call_id, "type": "function",
                                "function": {"name": call["name"], "arguments": json.dumps(call["args"])}}],
            })
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": call_id, "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out
