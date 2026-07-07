"""
tools/web_search.py

On-demand web search, used only when the chat agent explicitly needs
to go beyond the local knowledge base. Uses SerpAPI if a key is
configured, otherwise falls back to scraping DuckDuckGo's HTML
endpoint (no API key required).
"""

import os
import requests
from bs4 import BeautifulSoup

_UA = "Mozilla/5.0 (compatible; tech-lookout/1.0)"


def _serpapi_search(query: str, limit: int) -> list[dict]:
    resp = requests.get(
        "https://serpapi.com/search",
        params={"q": query, "api_key": os.environ["SERPAPI_KEY"], "engine": "google"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("organic_results", [])[:limit]:
        results.append({
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
        })
    return results


def _duckduckgo_search(query: str, limit: int) -> list[dict]:
    resp = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": _UA},
        timeout=10,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for result in soup.select(".result")[:limit]:
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        results.append({
            "url": link.get("href", ""),
            "title": link.get_text(strip=True),
            "snippet": snippet.get_text(strip=True) if snippet else "",
        })
    return results


def web_search(query: str, limit: int = 5) -> list[dict]:
    if os.environ.get("SERPAPI_KEY"):
        return _serpapi_search(query, limit)
    return _duckduckgo_search(query, limit)
