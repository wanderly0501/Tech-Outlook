"""
chat_agent.py

Always-on interactive agent. User talks to it; it answers from
the local knowledge base, optionally doing web search for deep dives.

Write permissions: conversations table, memory/preferences.md, memory/user_history.md
Read permissions:  articles.db (all tables), all memory/*.md files
"""

from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import anthropic

from core.agent_loop import run_agent_loop, build_system_prompt
from tools.config import PROMPTS_DIR, MEMORY_DIR
from tools import db

MEMORY_PATHS = [
    str(MEMORY_DIR / "session.md"),
    str(MEMORY_DIR / "preferences.md"),
    str(MEMORY_DIR / "user_history.md"),
    str(MEMORY_DIR / "top_of_mind.md"),
]

BASE_SYSTEM_PROMPT = (Path(PROMPTS_DIR) / "chat_agent.md").read_text(encoding="utf-8")

TOOLS = [
    {
        "name": "search_kb",
        "description": "Search the local knowledge base of stored articles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
                "mode": {
                    "type": "string",
                    "enum": ["text", "topic", "date"],
                    "description": "text=full-text search, topic=filter by topic, date=filter by date range",
                },
                "topic": {"type": "string", "description": "Topic filter (mode=topic)"},
                "date_from": {"type": "string", "description": "ISO date, e.g. 2026-07-01"},
                "date_to": {"type": "string", "description": "ISO date, e.g. 2026-07-05"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_history",
        "description": "Search past conversation logs for things discussed in prior sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "date_from": {"type": "string", "description": "ISO date, e.g. 2026-06-28"},
                "date_to": {"type": "string", "description": "ISO date, e.g. 2026-07-05"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for current information beyond the knowledge base.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_memory",
        "description": "Update a memory file. Chat agent controls preferences and user_history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "enum": ["preferences", "user_history"]},
                "content": {"type": "string", "description": "Full new content"},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["file", "content"],
        },
    },
]


def dispatch(tool_name: str, tool_input: dict) -> dict:
    from tools.search_kb import search_kb
    from tools.search_history import search_history
    from tools.web_search import web_search
    from tools.update_memory import update_memory

    handlers = {
        "search_kb": search_kb,
        "search_history": search_history,
        "web_search": web_search,
        "update_memory": lambda **kw: update_memory(caller="chat", **kw),
    }

    if tool_name not in handlers:
        return {"error": f"Unknown tool: {tool_name}"}

    return handlers[tool_name](**tool_input)


def _flatten_message(message: dict) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if hasattr(block, "type") and block.type == "text":
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "tool_result":
            parts.append(str(block.get("content", "")))
    return " ".join(parts)


def _summarize_session(messages: list[dict]) -> str:
    """Ask Claude for a 2-3 line summary of the session, for storage/search."""
    transcript = "\n".join(
        f"{m['role']}: {_flatten_message(m)}" for m in messages if _flatten_message(m).strip()
    )
    if not transcript.strip():
        return "Empty session."

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system="Summarize this chat session in 2-3 lines: topics discussed and any open threads.",
        messages=[{"role": "user", "content": transcript[:12000]}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def save_conversation(messages: list[dict], started_at: str):
    db.init_db()
    summary = _summarize_session(messages)
    safe_messages = [
        {"role": m["role"], "content": _flatten_message(m)} for m in messages
    ]
    db.insert_conversation(
        started_at=started_at,
        ended_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        messages=safe_messages,
    )


def main():
    print("Tech Lookout — type 'quit' to exit\n")

    db.init_db()
    started_at = datetime.now(timezone.utc).isoformat()
    system_prompt = build_system_prompt(BASE_SYSTEM_PROMPT, MEMORY_PATHS)
    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        print("Agent: ", end="", flush=True)

        run_agent_loop(
            messages=messages,
            system_prompt=system_prompt,
            tools=TOOLS,
            dispatch=dispatch,
            on_text=lambda t: print(t, end="", flush=True),
        )

        print()

    if messages:
        save_conversation(messages, started_at)
        print("[session saved]")


if __name__ == "__main__":
    main()
