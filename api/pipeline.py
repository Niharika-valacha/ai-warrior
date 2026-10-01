"""Level 0 data pipeline: turn a raw support-chat export into requirements.

    ingest → clean → redact PII → label intents → check the labeler → measure baseline → requirements

Each stage is a small pure function, so it can be tested on its own and swapped later
(e.g. an LLM labeler instead of keywords) without touching the others.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean
from typing import Optional

from intents import classify

REQUIRED_FIELDS = ("ticket_id", "created_at", "channel", "text", "first_response_min", "resolved")


@dataclass(frozen=True)
class Chat:
    ticket_id: str
    created_at: str
    channel: str
    text: str
    first_response_min: int
    resolved: bool
    csat: Optional[int] = None  # 1–5, None if the customer didn't rate
    label: Optional[str] = None  # human-assigned intent, on a sample only


# ---------------------------------------------------------------- ingest + clean


def ingest(path: Path) -> tuple[list[dict], list[dict]]:
    """Read the export. Returns (valid records, rejected records with the reason)."""
    valid, rejected = [], []
    for record in json.loads(path.read_text()):
        missing = [f for f in REQUIRED_FIELDS if f not in record]
        if missing:
            rejected.append({"ticket_id": record.get("ticket_id"), "reason": f"missing {', '.join(missing)}"})
        else:
            valid.append(record)
    return valid, rejected


def clean(records: list[dict]) -> tuple[list[Chat], dict]:
    """Normalize whitespace, drop empty chats, keep the first copy of each ticket."""
    seen, chats, dropped = set(), [], Counter()
    for r in records:
        text = " ".join(r["text"].split())
        if not text:
            dropped["empty"] += 1
        elif r["ticket_id"] in seen:
            dropped["duplicate"] += 1
        else:
            seen.add(r["ticket_id"])
            chats.append(Chat(**{**{k: r.get(k) for k in Chat.__dataclass_fields__}, "text": text}))
    return chats, dict(dropped)


# ---------------------------------------------------------------- PII

# Order matters: UPI IDs look like emails without a domain, cards are long digit runs.
PII_PATTERNS = {
    "UPI": re.compile(r"\b[\w.-]+@(?:ok\w+|ybl|paytm|upi|axl|ibl)\b", re.I),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "CARD": re.compile(r"\b(?:\d[ -]?){12,15}\d\b"),
    "PHONE": re.compile(r"(?:\+91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b"),
}


def redact_text(text: str) -> tuple[str, Counter]:
    found = Counter()
    for kind, pattern in PII_PATTERNS.items():
        text, n = pattern.subn(f"[{kind}]", text)
        found[kind] += n
    return text, +found  # unary + drops zero counts


def redact(chats: list[Chat]) -> tuple[list[Chat], dict]:
    """Mask personal data before anything else reads the chats."""
    out, total = [], Counter()
    for chat in chats:
        text, found = redact_text(chat.text)
        total += found
        out.append(replace(chat, text=text))
    return out, dict(total)


# ---------------------------------------------------------------- label + check the labeler


def label(chats: list[Chat]) -> list[tuple[Chat, str]]:
    # ponytail: keyword labeler. Swap for an LLM or embedding classifier when accuracy (below) isn't enough.
    return [(chat, classify(chat.text)) for chat in chats]


def labeler_accuracy(labeled: list[tuple[Chat, str]]) -> dict:
    """Score the labeler against the human-labeled sample. Never trust a classifier you haven't measured."""
    checked = [(c, got) for c, got in labeled if c.label]
    misses = [{"ticket_id": c.ticket_id, "text": c.text, "human": c.label, "labeler": got} for c, got in checked if got != c.label]
    accuracy = 1 - len(misses) / len(checked) if checked else None
    return {"checked": len(checked), "accuracy": accuracy, "misses": misses}


# ---------------------------------------------------------------- measure + requirements


def baseline(labeled: list[tuple[Chat, str]]) -> dict:
    """Today's numbers per intent, with humans doing the work: what the AI has to beat."""
    by_intent: dict[str, list[Chat]] = {}
    for chat, intent in labeled:
        by_intent.setdefault(intent, []).append(chat)
    total = len(labeled)
    stats = {}
    for intent, chats in sorted(by_intent.items(), key=lambda kv: -len(kv[1])):
        rated = [c.csat for c in chats if c.csat is not None]
        stats[intent] = {
            "share": round(len(chats) / total, 2),
            "chats": len(chats),
            "avg_first_response_min": round(mean(c.first_response_min for c in chats)),
            "resolved_rate": round(sum(c.resolved for c in chats) / len(chats), 2),
            "avg_csat": round(mean(rated), 1) if rated else None,
        }
    return stats


FUNCTIONAL = {
    "order_status": "Answer order status from live order data",
    "refund": "Handle refund requests within policy, escalate the rest",
    "address": "Change the delivery address before pickup",
    "other": "Hand off to a human",
}


def requirements(stats: dict, coverage: float = 0.8) -> dict:
    """Automate the biggest intents first, until they cover `coverage` of all chats."""
    automate, covered = [], 0.0
    for intent, s in stats.items():
        if covered >= coverage:
            break
        if intent == "other":  # a grab bag, not one thing to automate
            continue
        automate.append(intent)
        covered += s["share"]
    return {
        "automate_first": automate,
        "covers": f"{covered:.0%} of chats",
        "functional": [FUNCTIONAL[i] for i in automate],
        "non_functional": {
            "reply_time": "under 3 seconds (today: hours)",
            "cost": "under ₹0.50 per chat",
            "privacy": "PII redacted before any model sees a chat",
        },
        "success": {"resolved_without_human": "80%", "csat": "4.0 or better"},
    }


def golden_candidates(labeled: list[tuple[Chat, str]], per_intent: int = 3) -> dict:
    """A few redacted chats per intent to seed the eval set (Level 10)."""
    picked: dict[str, list[str]] = {}
    for chat, intent in labeled:
        if len(picked.setdefault(intent, [])) < per_intent:
            picked[intent].append(chat.text)
    return picked
