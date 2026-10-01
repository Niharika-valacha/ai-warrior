"""Support intents and the keywords that signal them. Shared by Level 0 analytics and the replay model."""
from __future__ import annotations

INTENT_WORDS = {
    "refund": ["refund", "money back", "cold", "missing", "damaged", "wrong item"],
    "order_status": ["where", "late", "status", "kab", "eta", "arrive", "coming", "track", "rider"],
    "address": ["address", "location"],
}


def classify(text: str) -> str:
    """First intent whose keywords appear in the text, else "other"."""
    lowered = text.lower()
    return next((intent for intent, words in INTENT_WORDS.items() if any(w in lowered for w in words)), "other")
