"""Web search via Tavily (https://tavily.com), used to ground side quests and live follow-up answers."""
from __future__ import annotations

import json
import os
import urllib.request

URL = "https://api.tavily.com/search"
TIMEOUT_S = 15


class SearchUnavailable(RuntimeError):
    pass


def search(query: str, max_results: int = 5) -> list[dict]:
    """Top web results as [{title, url, content}]. Raises SearchUnavailable without a key or on failure."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise SearchUnavailable("TAVILY_API_KEY is not set in api/.env")
    request = urllib.request.Request(
        URL,
        data=json.dumps({"query": query, "max_results": max_results, "search_depth": "basic"}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "ai-warrior/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as res:
            results = json.load(res).get("results", [])
    except Exception as err:
        raise SearchUnavailable(f"Tavily search failed: {type(err).__name__}") from err
    return [{"title": r.get("title", ""), "url": r["url"], "content": r.get("content", "")} for r in results if r.get("url")]
