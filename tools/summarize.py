"""
tools/summarize.py

Non-agentic Claude API call used inside the crawl tool to summarize each
new article as it's ingested, and to extract a keyword list for it in
the same call. This is deliberately a plain function call (not a step
in the ReAct loop) — summarizing and keyword-tagging are mechanical,
not judgment calls that need tool-use overhead.

Keyword extraction is per-article and stateless — each call only ever
sees that one article's own title/content, never other articles or a
running vocabulary. That's intentional: it keeps this independent of
any clustering/consolidation step (there isn't one anymore), so a
document's keywords never depend on crawl order or what else was in
the batch.
"""

import json
import re

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_KEYWORDS = 10

_SYSTEM_PROMPT = (
    "Summarize the tech news article in under 100 words. Plain English, "
    "no jargon unless essential, no filler like 'this article discusses'. "
    "This summary is the only copy of the article kept in the knowledge "
    "base (the full text is discarded), so capture the concrete facts — "
    "who, what, numbers, why it matters — not just the gist.\n\n"
    f"Also extract up to {MAX_KEYWORDS} short keywords/phrases for this "
    "article specifically, based only on its own content — company and "
    "product names, technologies, people, and the general subject areas it "
    "touches (e.g. 'xbox', 'layoffs', 'ai hardware', 'antitrust'). These "
    "are used to make the article findable in search later, so favor "
    "concrete, distinctive terms over generic ones.\n\n"
    "Respond with ONLY a JSON object, no markdown code fences, no other "
    'text: {"summary": "...", "keywords": ["...", "..."]}'
)


def summarize_article(title: str, content: str) -> dict:
    """Returns {"summary": str, "keywords": list[str]}."""
    client = anthropic.Anthropic()
    text = content[:8000]  # keep prompts small; body is plenty for a summary
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Title: {title}\n\n{text}"}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text").strip()
    return _parse_response(raw)


def _parse_response(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            summary = str(data.get("summary", "")).strip()
            keywords = data.get("keywords", [])
            if summary and isinstance(keywords, list):
                clean_keywords = [str(k).strip().lower() for k in keywords if str(k).strip()]
                return {"summary": summary, "keywords": clean_keywords[:MAX_KEYWORDS]}
        except json.JSONDecodeError:
            pass
    # Fallback if Claude didn't return valid JSON — keep the summary usable,
    # just without keywords, rather than losing the whole article.
    return {"summary": raw, "keywords": []}
