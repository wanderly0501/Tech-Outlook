"""
tools/summarize.py

Non-agentic Claude API call used inside the crawl tool to summarize
each new article as it's ingested. This is deliberately a plain
function call (not a step in the ReAct loop) — summarizing is
mechanical, not a judgment call, so it doesn't need tool-use overhead.
"""

import anthropic

MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = (
    "Summarize the tech news article in under 100 words. Plain English, "
    "no jargon unless essential, no filler like 'this article discusses'. "
    "This summary is the only copy of the article kept in the knowledge "
    "base (the full text is discarded), so capture the concrete facts — "
    "who, what, numbers, why it matters — not just the gist. Output only "
    "the summary."
)


def summarize_article(title: str, content: str) -> str:
    client = anthropic.Anthropic()
    text = content[:8000]  # keep prompts small; body is plenty for a summary
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Title: {title}\n\n{text}"}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
