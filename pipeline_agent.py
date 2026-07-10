"""
pipeline_agent.py

Scheduled autonomous agent. Runs daily via scheduler.py.
No user interaction — crawls, processes, stores, reports.

Write permissions: articles.db (articles, reports), memory/pipeline_session.md, memory/top_of_mind.md
Read permissions:  everything
"""

import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core.agent_loop import run_agent_loop, build_system_prompt
from tools.config import PROMPTS_DIR, MEMORY_DIR
from tools import db

MEMORY_PATHS = [
    str(MEMORY_DIR / "pipeline_session.md"),
    str(MEMORY_DIR / "top_of_mind.md"),
]

BASE_SYSTEM_PROMPT = (Path(PROMPTS_DIR) / "pipeline_agent.md").read_text(encoding="utf-8")

TOOLS = [
    {
        "name": "crawl",
        "description": (
            "Fetch, summarize, keyword-tag, topic-cluster, and store today's new articles "
            "from a tech website. Returns the newly ingested articles "
            "(already deduplicated against the knowledge base)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site": {"type": "string", "enum": ["theverge"]},
                "date": {"type": "string", "description": "ISO date string, e.g. 2026-07-05"},
            },
            "required": ["site", "date"],
        },
    },
    {
        "name": "search_kb",
        "description": "Search articles already stored in the knowledge base.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["text", "topic", "keyword", "date"],
                    "description": "Prefer keyword over topic: topic requires an exact match against a dynamically-generated cluster label, while keyword does a forgiving substring match against per-article terms.",
                },
                "topic": {"type": "string", "description": "Exact match, must match a real cluster label"},
                "keyword": {"type": "string", "description": "Substring match, preferred over topic"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_memory",
        "description": "Update a memory file. Pipeline agent controls pipeline_session and top_of_mind.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "enum": ["pipeline_session", "top_of_mind"]},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["file", "content"],
        },
    },
    {
        "name": "write_report",
        "description": "Write a daily or weekly HTML/MD report with optional charts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Report body in markdown"},
                "format": {"type": "string", "enum": ["html", "md"], "default": "html"},
                "report_type": {"type": "string", "enum": ["daily", "weekly"], "default": "daily"},
                "date": {"type": "string", "description": "ISO date, defaults to today"},
                "charts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["pie", "bar", "timeline"]},
                            "title": {"type": "string"},
                            "data": {"type": "object", "description": "label→value pairs"},
                        },
                    },
                    "description": "Chart specs to embed in the report",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "send",
        "description": "Send the report to the user interface and/or email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": ["interface", "email", "both"]},
                "report_path": {"type": "string"},
                "subject": {"type": "string"},
                "recipient": {"type": "string"},
            },
            "required": ["target", "report_path"],
        },
    },
]


def dispatch(tool_name: str, tool_input: dict) -> dict:
    from tools.crawler import crawl
    from tools.search_kb import search_kb
    from tools.update_memory import update_memory
    from tools.write_report import write_report
    from tools.send import send

    handlers = {
        "crawl": crawl,
        "search_kb": search_kb,
        "update_memory": lambda **kw: update_memory(caller="pipeline", **kw),
        "write_report": write_report,
        "send": send,
    }

    if tool_name not in handlers:
        return {"error": f"Unknown tool: {tool_name}"}

    return handlers[tool_name](**tool_input)


def run_pipeline(date: str | None = None):
    db.init_db()

    target_date = date or datetime.now().strftime("%Y-%m-%d")
    is_friday = datetime.fromisoformat(target_date).weekday() == 4
    print(f"[pipeline] Starting run for {target_date}")

    system_prompt = build_system_prompt(BASE_SYSTEM_PROMPT, MEMORY_PATHS)

    trigger = f"Run the full daily pipeline for {target_date}. Site: theverge."
    if is_friday:
        trigger += (
            " Today is Friday — after the daily report, also generate the "
            "weekly report covering the past 7 days."
        )

    messages = [{"role": "user", "content": trigger}]

    result = run_agent_loop(
        messages=messages,
        system_prompt=system_prompt,
        tools=TOOLS,
        dispatch=dispatch,
        on_text=lambda t: print(t, end="", flush=True),
    )

    print(f"\n[pipeline] Completed for {target_date}")
    return result


if __name__ == "__main__":
    cli_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(date=cli_date)
