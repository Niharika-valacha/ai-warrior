"""The one place the system talks to a language model.

complete() returns one of:
  {"text": str}                                   a normal reply
  {"json": dict}                                  when `schema` is given
  {"tool_call": {"name": str, "args": dict}}      when the model wants a tool
Every reply also carries "model": which provider and model actually answered.

Providers are tried in order (LLM_PROVIDERS in .env, default "groq,gemini"); any without a key is
skipped. If every provider fails, complete() falls back to the replay model so a demo never breaks,
while generate() raises, because some content (side quests, live answers) must never be made up.
This is model routing with fallbacks: the same pattern production systems use when a provider has
an outage or rate-limits you, and it keeps the project on free tiers.
"""
from __future__ import annotations

import contextvars
import json
import os
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

import replay

TIMEOUT_S = 12


@dataclass(frozen=True)
class Provider:
    name: str
    url: str  # an OpenAI-compatible chat completions endpoint
    key_env: str
    model_env: str
    default_model: str
    extra: dict = field(default_factory=dict)  # provider-specific request fields

    @property
    def key(self) -> str:
        return os.environ.get(self.key_env, "")

    @property
    def model(self) -> str:
        return os.environ.get(self.model_env) or self.default_model


PROVIDERS = {
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1/chat/completions",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
        {"reasoning_effort": "low"},
    ),
    "gemini": Provider(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "gemini-2.5-flash",  # model names change: list current ones at .../v1beta/openai/models
    ),
}


class LLMUnavailable(RuntimeError):
    pass


def chain() -> list[Provider]:
    """Configured providers that have a key, in the order they should be tried."""
    names = os.environ.get("LLM_PROVIDERS", "groq,gemini").split(",")
    return [PROVIDERS[n.strip()] for n in names if n.strip() in PROVIDERS and PROVIDERS[n.strip()].key]


# ---------------------------------------------------------------- live vs replay, per run

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


def _record(model: str) -> None:
    used = _used.get()
    if used is not None:
        used.add(model)


# ---------------------------------------------------------------- the two entry points


def complete(
    messages: list[dict],
    system: Optional[str] = None,
    schema: Optional[dict] = None,
    tools: Optional[list[dict]] = None,
) -> dict:
    """For demos: try each provider, then fall back to the replay model. Never raises."""
    if _live.get():
        try:
            reply = _first_success(messages, system, schema, tools, TIMEOUT_S)
            _record(reply["model"])
            return reply
        except LLMUnavailable as err:
            _record(f"replay ({err})")
    else:
        _record("replay")
    return {**replay.respond(messages, system=system, schema=schema, tools=tools), "model": "replay"}


def generate(messages: list[dict], system: str, schema: Optional[dict] = None, timeout: int = 45) -> dict:
    """For content that must be real: try each provider; if all fail, raise LLMUnavailable."""
    return _first_success(messages, system, schema, None, timeout)


def _first_success(messages, system, schema, tools, timeout) -> dict:
    providers = chain()
    if not providers:
        raise LLMUnavailable("No LLM provider configured: set GROQ_API_KEY or GEMINI_API_KEY in api/.env")
    failures = []
    for provider in providers:
        try:
            return {**_call(provider, messages, system, schema, tools, timeout), "model": f"{provider.name}/{provider.model}"}
        except urllib.error.HTTPError as err:
            failures.append(f"{provider.name} HTTP {err.code}" + (" (rate limited)" if err.code == 429 else ""))
        except Exception as err:  # timeout, connection error, malformed reply
            failures.append(f"{provider.name} {type(err).__name__}")
    raise LLMUnavailable("All providers failed: " + ", ".join(failures))


# ---------------------------------------------------------------- one OpenAI-compatible call


def _call(
    provider: Provider,
    messages: list[dict],
    system: Optional[str],
    schema: Optional[dict],
    tools: Optional[list[dict]],
    timeout: int,
) -> dict:
    if schema:
        system = f"{system or ''}\nReply with only a JSON object matching this JSON Schema:\n{json.dumps(schema)}"
    body: dict = {
        "model": provider.model,
        "messages": ([{"role": "system", "content": system}] if system else []) + _to_openai(messages),
        **provider.extra,
    }
    if schema:
        body["response_format"] = {"type": "json_object"}
    if tools:
        body["tools"] = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
            for t in tools
        ]

    request = urllib.request.Request(
        provider.url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {provider.key}",
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
