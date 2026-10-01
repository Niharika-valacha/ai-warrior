"""Replay model: a deterministic stand-in for the LLM, so every demo runs offline and identically.

It plays the role a real model would: it reads the same messages, system prompt, schema and tools,
and answers in the same shapes. The system code can't tell the difference, which is the point.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from intents import classify

ORDER_ID = re.compile(r"#?\b(\d{4})\b")


def respond(
    messages: list[dict],
    system: Optional[str] = None,
    schema: Optional[dict] = None,
    tools: Optional[list[dict]] = None,
) -> dict:
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    if schema:
        return {"json": _extract_ticket(messages[-1]["content"])}
    if tools:
        return _agent_turn(user, messages, {t["name"] for t in tools})
    if system and system.startswith("Answer only from the policy"):
        return {"text": _grounded_answer(system)}
    if system and system.startswith("Summarize"):
        return {"text": _summary(messages)}
    if system:
        return {"text": "Sorry about that! 😔 Can you share your order ID? I'll check what I can do."}
    return {"text": _plain_chat(messages)}


# ---------- plain chat (no system prompt) ----------


def _plain_chat(messages: list[dict]) -> str:
    last = messages[-1]["content"].lower()
    if "where is it" in last:
        earlier = " ".join(m["content"].lower() for m in messages[:-1])
        return "Let me check where your order is!" if "order" in earlier else "Where is… what, exactly? 🤔"
    return "Sorry about that! Let me help."


# ---------- structured output ----------

def _extract_ticket(text: str) -> dict:
    lowered = text.lower()
    intent = classify(text)
    match = ORDER_ID.search(text)
    urgent = text.isupper() or any(w in lowered for w in ("starving", "urgent", "asap", "!!"))
    return {"intent": intent, "order_id": match.group(1) if match else None, "urgency": "high" if urgent else "normal"}


# ---------- RAG ----------


def _grounded_answer(system: str) -> str:
    sections = re.findall(r"§([\d.]+) [^:]+: ([^.]+\.)", system)
    if not sections:
        return "I couldn't find that in our policy, so let me get a human to help."
    body = " ".join(sentence for _, sentence in sections)
    cites = ", ".join(f"§{sid}" for sid, _ in sections)
    return f"{body} ({cites})"


# ---------- memory ----------


def _summary(messages: list[dict]) -> str:
    text = " ".join(m["content"] for m in messages)
    order = ORDER_ID.search(text)
    return f"Customer is chasing late order #{order.group(1) if order else '?'} and asked about toppings and the address."


# ---------- tool use / agent turns ----------


def _agent_turn(user: str, messages: list[dict], tool_names: set[str]) -> dict:
    results = {m["name"]: json.loads(m["content"]) for m in messages if m["role"] == "tool"}
    match = ORDER_ID.search(user)
    if not match:
        return {"text": "Could you share your order ID?"}
    order_id = match.group(1)

    # Level 5: one tool, one answer.
    if "get_order_status" in tool_names:
        if "get_order_status" not in results:
            return _call("get_order_status", order_id=order_id)
        r = results["get_order_status"]
        if "error" in r:
            return {"text": "I couldn't find that order on your account."}
        return {"text": f"Your order is {r['eta_min']} minutes away! 🛵"}

    # Level 9: a jailbreak fools the model into asking for a huge refund.
    injected = re.search(r"refund ₹?([\d,]+)", user, re.I)
    if "ignore" in user.lower() and injected:
        if "issue_refund" not in results:
            amount = int(injected.group(1).replace(",", ""))
            return _call("issue_refund", order_id=order_id, amount=amount, reason="customer request")
        return {"text": "I can't process that refund. If something was wrong with your order, I'm happy to check it! 😊"}

    # Level 7: refund for a missing item, one step at a time.
    if "get_order" not in results:
        return _call("get_order", order_id=order_id)
    order = results["get_order"]
    if order.get("status") != "delivered":
        return {"text": "Your order is still on its way 🛵 Once it's delivered, I can help with anything missing."}
    if "search_policy" not in results:
        return _call("search_policy", query="missing item refund")
    if "get_payment" not in results:
        return _call("get_payment", order_id=order_id)
    if "issue_refund" not in results:
        missing = next((i for i in order["items"] if i["name"].lower() in user.lower()), order["items"][-1])
        return _call("issue_refund", order_id=order_id, amount=missing["price"], reason=f"missing {missing['name'].lower()}")
    refund = results["issue_refund"]
    method = results["get_payment"]["method"]
    return {
        "text": f"So sorry about that! 😔 ₹{refund['amount']} is on its way to your {method} (ref {refund['refund_id']})."
    }


def _call(name: str, **args) -> dict:
    return {"tool_call": {"name": name, "args": args}}
