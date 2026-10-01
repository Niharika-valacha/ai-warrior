"""FoodieGo AI support agent: the real code behind each level of the quiz.

Every function here runs for real against FoodieGo's SQLite database and policy docs.
`trace(...)` calls are what X-ray mode shows, step by step.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional

from pydantic import BaseModel, ValidationError

import db
import llm
import pipeline
from tracer import quiet, trace

DATA = Path(__file__).parent / "data"


def load(name: str):
    return json.loads((DATA / name).read_text())


def approx_tokens(messages: list[dict]) -> int:
    return sum(len(m.get("content") or "") for m in messages) // 4  # ~4 characters per token


# ---------------------------------------------------------------- Level 0: requirements

def analyze_chats() -> dict:
    """Lesson: understand the problem with data before writing any AI code."""
    # Step 1: read the raw export from the ticketing tool; reject broken records instead of guessing.
    records, rejected = pipeline.ingest(DATA / "support_export.json")
    trace("ingest the ticket export (synthetic, for the demo)", records=len(records), rejected=rejected)

    # Step 2: real exports are messy. Remove duplicates and empty chats.
    chats, dropped = pipeline.clean(records)
    trace("clean: normalize, drop empties and duplicates", kept=len(chats), dropped=dropped)

    # Step 3: privacy first. Mask phones, emails, UPI IDs and cards BEFORE anyone (or any model) reads them.
    chats, pii = pipeline.redact(chats)
    trace("redact PII before anything reads the chats", masked=pii, example=next(c.text for c in chats if "[" in c.text))

    # Step 4: tag every chat with what the customer wanted.
    labeled = pipeline.label(chats)
    trace("label every chat with an intent", counts=dict(Counter(intent for _, intent in labeled)))

    # Step 5: never trust a classifier you haven't measured. Compare against human labels.
    check = pipeline.labeler_accuracy(labeled)
    trace("check the labeler against human labels", checked=check["checked"], accuracy=f"{check['accuracy']:.0%}", misses=check["misses"])

    # Step 6: today's numbers (response time, CSAT) are the bar the AI has to beat.
    stats = pipeline.baseline(labeled)
    trace("measure today's baseline per intent", baseline=stats)

    # Step 7: automate the biggest problems first, and decide how we'll measure success.
    reqs = pipeline.requirements(stats)
    trace("requirements: what to automate first, and how we'll know it works", requirements=reqs)

    # Step 8: the same real chats become test cases later (Level 10: evals).
    golden = pipeline.golden_candidates(labeled)
    trace("seed the eval set with real (redacted) examples", golden_candidates=golden)
    return reqs


# ---------------------------------------------------------------- Level 1: stateless LLM call


def chat(history: list[dict], message: str) -> list[dict]:
    """Lesson: the model remembers nothing. Your backend sends the whole conversation every time."""
    # Add the new message to everything said so far.
    history = history + [{"role": "user", "content": message}]
    trace("send the WHOLE history: the API remembers nothing", messages=history, tokens=approx_tokens(history))

    # One API call. The model only knows what's inside `history`, nothing else.
    reply = llm.complete(history)
    trace("model replied", reply=reply["text"])
    # Save the reply too, so the next call includes it. This list IS the memory.
    return history + [{"role": "assistant", "content": reply["text"]}]


# ---------------------------------------------------------------- Level 2: system prompt

# The rules, written by us (the builders), not by the customer.
SYSTEM_PROMPT = """You are FoodieGo's support agent. Be brief and kind.
Only help with orders, refunds and delivery addresses.
Never promise refunds, free food, coupons or any compensation yourself:
only the refund tool decides, and refunds over ₹500 need a human."""


def reply_with_rules(message: str) -> str:
    """Lesson: set the bot's role, tone and limits before the user says anything."""
    trace("rules are set before the user speaks", system=SYSTEM_PROMPT)

    # The system prompt travels with every call, separate from what the user typed.
    reply = llm.complete([{"role": "user", "content": message}], system=SYSTEM_PROMPT)
    trace("model replied, inside the rules", reply=reply["text"])
    return reply["text"]


# ---------------------------------------------------------------- Level 3: structured output


# The exact shape our backend needs. Anything else is rejected.
class Ticket(BaseModel):
    intent: Literal["order_status", "refund", "address", "other"]
    order_id: Optional[str]
    urgency: Literal["normal", "high"]


def route_ticket(message: str) -> Ticket:
    """Lesson: don't ask the model for JSON politely. Enforce a schema, then validate in code."""
    # Turn the Python class into a JSON Schema the API can enforce.
    schema = Ticket.model_json_schema()
    trace("the API must return JSON matching this schema", schema=schema)

    reply = llm.complete([{"role": "user", "content": message}], system="Extract a support ticket.", schema=schema)
    trace("model returned", raw=reply["json"])

    # Trust, but verify: our code checks every field before the ticket goes anywhere.
    try:
        ticket = Ticket.model_validate(reply["json"])
    except ValidationError as err:
        trace("rejected: does not match the schema", error=str(err))
        raise
    trace("validated in code, safe to route", queue=f"{ticket.intent}/{ticket.urgency}", ticket=ticket)
    return ticket


# ---------------------------------------------------------------- Level 4: RAG

STOPWORDS = set("a an the i me my is was to of for and or can get it in on at be this that with".split())


def words(text: str) -> list[str]:
    return [w.rstrip("s") for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def search_policy(query: str, k: int = 2) -> list[dict]:
    """The "R" in RAG: find the few policy sections that match the question."""
    # ponytail: keyword-overlap ranking. Production uses embeddings + a vector DB; same idea, better recall.
    query_words = set(words(query))
    ranked = sorted(
        load("policies.json"),
        key=lambda s: -sum(words(s["title"] + " " + s["text"]).count(w) for w in query_words),
    )
    hits = ranked[:k]  # only the top k: less text means cheaper, faster and more focused answers
    trace("retrieve the most relevant policy sections", query=query, hits=[f"§{h['id']} {h['title']}" for h in hits])
    return hits


def answer_policy(question: str) -> str:
    """Lesson: an open-book exam. Look it up first, then answer only from what you found."""
    # 1. Retrieve: search the real policy docs.
    hits = search_policy(question)
    # 2. Augment: paste just those sections into the instructions.
    context = "\n".join(f"§{h['id']} {h['title']}: {h['text']}" for h in hits)
    system = "Answer only from the policy sections below, and cite them.\n\n" + context
    trace("the model only sees these sections", context=context)

    # 3. Generate: the answer is grounded in today's policy, with citations. No retraining needed.
    reply = llm.complete([{"role": "user", "content": question}], system=system)
    trace("grounded answer, with citations", reply=reply["text"])
    return reply["text"]


# ---------------------------------------------------------------- Level 5: tool calling

# A "menu" we show the model: what the tool is called, what it does, what input it needs.
ORDER_STATUS_TOOL = {
    "name": "get_order_status",
    "description": "Live status of one of the customer's orders.",
    "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
}


def get_order_status(order_id: str, user_id: str) -> dict:
    """The tool itself: plain backend code we wrote. The model never touches the database."""
    # Parameterized SQL (the `?`) so nothing the model sends can inject SQL.
    row = db.one("SELECT user_id, status, eta_min FROM orders WHERE id = ?", order_id)
    # Security check in code: you can only see YOUR orders.
    if row is None or row["user_id"] != user_id:
        trace("blocked: not this customer's order", order_id=order_id)
        return {"error": "order not found"}
    result = {"order_id": order_id, "status": row["status"], "eta_min": row["eta_min"]}
    trace("YOUR code ran the query on the live database", result=result)
    return result


def answer_with_tool(message: str, user_id: str) -> str:
    """Lesson: the model ASKS for a tool. Your code decides whether to run it."""
    messages = [{"role": "user", "content": message}]
    # 1. The model reads the menu and replies "please call get_order_status(4521)".
    reply = llm.complete(messages, system=SYSTEM_PROMPT, tools=[ORDER_STATUS_TOOL])
    call = reply["tool_call"]
    trace("model asked for a tool. It can't run anything itself", tool_call=call)

    # 2. OUR code runs it. Who the user is comes from the login session, never from the model.
    result = get_order_status(call["args"]["order_id"], user_id)
    # 3. Hand the result back so the model can phrase a friendly answer.
    messages += [
        {"role": "assistant", "tool_call": call},
        {"role": "tool", "name": call["name"], "content": json.dumps(result)},
    ]
    final = llm.complete(messages, system=SYSTEM_PROMPT, tools=[ORDER_STATUS_TOOL])
    trace("model turned the result into a reply", reply=final["text"])
    return final["text"]


# ---------------------------------------------------------------- Level 9: guardrails (used by the agent tools)

APPROVAL_LIMIT = 500  # ₹, policy §4.6


def issue_refund(order_id: str, amount: int, reason: str, user_id: str) -> dict:
    """Lesson: assume the model WILL be fooled. The money rules live here, in code, where prompts can't reach."""
    order = db.one("SELECT user_id, total FROM orders WHERE id = ?", order_id)
    # Rule 1: only your own orders.
    if order is None or order["user_id"] != user_id:
        return blocked(order_id, "not this customer's order")
    # Rule 2: never refund more than was paid, no matter how nicely the "grandma" asks.
    if amount > order["total"]:
        return blocked(order_id, f"₹{amount} is more than the order total of ₹{order['total']}")
    # Rule 3: big refunds wait for a human (human-in-the-loop).
    if amount > APPROVAL_LIMIT:
        db.run("INSERT INTO refunds (order_id, amount, reason, status) VALUES (?, ?, ?, 'pending_approval')", order_id, amount, reason)
        trace("over the limit: a human must approve", amount=amount, limit=APPROVAL_LIMIT)
        return {"status": "pending_approval"}

    # Every check passed: now, and only now, money moves.
    refund_id = db.run("INSERT INTO refunds (order_id, amount, reason, status) VALUES (?, ?, ?, 'issued')", order_id, amount, reason)
    trace("all checks passed in code: refund issued", amount=amount, reason=reason)
    return {"status": "issued", "refund_id": f"R-{refund_id}", "amount": amount}


def blocked(order_id: str, why: str) -> dict:
    # Write it to the audit log, so the security team can see attacks happening.
    db.run("INSERT INTO audit_log (event, detail) VALUES ('refund_blocked', ?)", f"order {order_id}: {why}")
    trace("BLOCKED by code, not by the prompt", reason=why, logged=True)
    return {"status": "blocked", "reason": why}


# ---------------------------------------------------------------- Level 6: MCP-style tool server


@dataclass
class Tool:
    description: str
    schema: dict
    fn: Callable[..., dict]


def get_order(order_id: str, user_id: str) -> dict:
    row = db.one("SELECT user_id, status, total, items FROM orders WHERE id = ?", order_id)
    if row is None or row["user_id"] != user_id:
        return {"error": "order not found"}
    return {"order_id": order_id, "status": row["status"], "total": row["total"], "items": json.loads(row["items"])}


def get_payment(order_id: str, user_id: str) -> dict:
    row = db.one(
        "SELECT p.method, p.amount FROM payments p JOIN orders o ON o.id = p.order_id WHERE p.order_id = ? AND o.user_id = ?",
        order_id,
        user_id,
    )
    return row or {"error": "payment not found"}


def policy_tool(query: str, user_id: str) -> dict:
    return {"sections": [f"§{h['id']} {h['title']}: {h['text']}" for h in search_policy(query)]}


def schema_of(**fields: str) -> dict:
    return {"type": "object", "properties": {f: {"type": t} for f, t in fields.items()}, "required": list(fields)}


# One registry of every tool. Add a tool here once, and every AI app can use it.
TOOLS = {
    "get_order": Tool("Look up one of the customer's orders.", schema_of(order_id="string"), get_order),
    "search_policy": Tool("Search FoodieGo's policy docs.", schema_of(query="string"), policy_tool),
    "get_payment": Tool("How the customer paid for an order.", schema_of(order_id="string"), get_payment),
    "issue_refund": Tool(
        "Refund part of an order.", schema_of(order_id="string", amount="integer", reason="string"), issue_refund
    ),
}


def handle_mcp(request: dict, user_id: str) -> dict:
    """Lesson: one standard plug. Every app asks the same two questions: "what tools?" and "run this one"."""
    # (Real MCP adds transports, auth and more. The contract is the same.)
    method = request["method"]
    if method == "tools/list":
        # "What can you do?" Any MCP client discovers tools at runtime, with no custom glue code.
        result = {"tools": [{"name": n, "description": t.description, "inputSchema": t.schema} for n, t in TOOLS.items()]}
    elif method == "tools/call":
        # "Run this tool with these arguments." Same call shape for every tool and every app.
        tool = TOOLS[request["params"]["name"]]
        result = {"content": tool.fn(**request["params"]["arguments"], user_id=user_id)}
    else:
        return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": f"unknown method {method}"}}
    trace(f"MCP {method}", client=request.get("client"), result=result)
    return {"jsonrpc": "2.0", "id": request["id"], "result": result}


# ---------------------------------------------------------------- Level 7: agent loop

TOOL_SPECS = [{"name": n, "description": t.description, "input_schema": t.schema} for n, t in TOOLS.items()]


def run_agent(message: str, user_id: str, max_steps: int = 10) -> str:
    """Lesson: an "agent" is just this loop. Think, use a tool, look at the result, repeat."""
    messages = [{"role": "user", "content": message}]
    for step in range(1, max_steps + 1):  # the brake: never loop forever and burn the budget
        # Think: the model decides the next step based on everything it has seen so far.
        reply = llm.complete(messages, system=SYSTEM_PROMPT, tools=TOOL_SPECS)
        if "tool_call" not in reply:
            # Done: no more tools needed, so this is the final answer.
            trace(f"step {step}: no tool needed, final answer", reply=reply["text"])
            return reply["text"]

        # Act: run the tool it asked for. Identity comes from the session, never from the model.
        call = reply["tool_call"]
        trace(f"step {step}: model asks for {call['name']}", args=call["args"])
        result = TOOLS[call["name"]].fn(**call["args"], user_id=user_id)
        trace(f"step {step}: result goes back to the model", result=result)
        # Observe: add the result to the conversation, then loop and think again.
        messages += [
            {"role": "assistant", "tool_call": call},
            {"role": "tool", "name": call["name"], "content": json.dumps(result)},
        ]

    # Too many steps: something is off, so hand over to a human instead of guessing.
    trace("hit max steps: hand off to a human", max_steps=max_steps)
    return "Let me get a human to help with this."


# ---------------------------------------------------------------- Level 8: memory / compaction

# Facts that must survive no matter how long the chat gets.
PIN_PATTERNS = {"order_id": r"#(\d{4})", "address": r"address to ([A-Z][\w ]+)"}


def compact(history: list[dict], keep_last: int = 10) -> list[dict]:
    """Lesson: a bigger notebook doesn't help if you can't find the page. Take better notes."""
    if len(history) <= keep_last:
        return history
    # Keep the latest messages word for word; everything older gets compressed.
    old, recent = history[:-keep_last], history[-keep_last:]

    # 1. Pin the key facts (order ID, address) so they can never get lost in the middle.
    pinned = {}
    for m in old:
        for key, pattern in PIN_PATTERNS.items():
            if match := re.search(pattern, m["content"]):
                pinned[key] = match.group(1)
    trace("pin the facts that must never be forgotten", pinned=pinned)

    # 2. Squash 70 old messages into one sentence.
    summary = llm.complete(old, system="Summarize this support chat in one sentence.")["text"]
    trace("summarize the old turns", turns=len(old), summary=summary)

    # 3. Next call sends: pinned facts + summary + recent messages. Far fewer tokens, nothing important lost.
    compacted = [{"role": "user", "content": f"Pinned facts: {json.dumps(pinned)}\nEarlier: {summary}"}] + recent
    trace("tokens sent per call", before=approx_tokens(history), after=approx_tokens(compacted))
    return compacted


# ---------------------------------------------------------------- Level 10: evals

RELEASE_GATE = 0.95  # below this score, we don't ship


def run_evals() -> dict:
    """Lesson: unit tests for AI. A fixed set of real cases, scored automatically, before every release."""
    # The golden set: real chats with the answer we expect, plus attack attempts.
    cases = load("golden.json")
    trace("load the golden set", cases=len(cases), kinds=dict(Counter(c["kind"] for c in cases)))

    # Run every case through the real system and record what went wrong.
    failures = []
    for case in cases:
        with quiet():
            passed, got = check_case(case)
        if not passed:
            failures.append({"input": case["input"], "expected": case.get("expect", "blocked"), "got": got})
    score = 1 - len(failures) / len(cases)
    trace("score every case with code checks", passed=len(cases) - len(failures), total=len(cases), failures=failures)

    # The release gate: a number decides, not a feeling or a public benchmark.
    ship = score >= RELEASE_GATE
    trace("release gate", score=f"{score:.0%}", gate=f"{RELEASE_GATE:.0%}", ship=ship)
    return {"score": score, "ship": ship, "failures": failures}


def check_case(case: dict) -> tuple[bool, str]:
    # Routing cases: did we pick the right intent?
    if case["kind"] == "route":
        intent = route_ticket(case["input"]).intent
        return intent == case["expect"], intent
    # Attack cases: the refund must NOT be issued.
    result = issue_refund(case["order_id"], case["amount"], reason="eval", user_id="u_42")
    return result["status"] != "issued", result["status"]
