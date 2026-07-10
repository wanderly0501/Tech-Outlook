# Tech Lookout — System Requirements

## Overview

A local Python agent system that crawls tech news daily, maintains a knowledge base, generates reports, and lets the user chat with it about tech trends — all without hitting the internet during chat.

Two separate processes. Zero shared state conflicts.

---

## Project Structure

```
agent/
├── core/
│   └── agent_loop.py          # shared ReAct loop
├── tools/
│   ├── crawler.py             # The Verge crawler
│   ├── search_kb.py           # SQLite FTS search
│   ├── search_history.py      # FTS search over past conversations
│   ├── web_search.py          # on-demand web search
│   ├── update_memory.py       # write memory/*.md files
│   ├── write_report.py        # HTML/MD report + charts
│   └── send.py                # deliver report
├── memory/
│   ├── pipeline_session.md    # current session context (pipeline writes)
│   ├── preferences.md         # user topic interests (chat writes)
│   ├── chat_session.md        # rolling digest of recent sessions (chat writes)
│   └── top_of_mind.md         # agent's daily highlights (pipeline writes)
├── knowledge/
│   └── articles.db            # SQLite database
├── reports/                   # generated HTML/MD reports
├── prompts/
│   ├── pipeline_agent.md      # system prompt for pipeline agent
│   └── chat_agent.md          # system prompt for chat agent
├── pipeline_agent.py          # scheduled autonomous agent
├── chat_agent.py              # always-on interactive agent
├── scheduler.py               # triggers pipeline_agent daily
└── requirements.txt
```

---

## Tech Stack

```
anthropic       # Claude API + tool calling
requests        # HTTP for crawler
beautifulsoup4  # HTML parsing
sqlite3         # knowledge base (stdlib)
scikit-learn    # TF-IDF topic clustering
schedule        # daily cron-like trigger
rich            # terminal UI for chat
python-dotenv   # .env for API key
```

---

## Agent 1: Pipeline Agent

### Trigger
- Runs daily at 08:00 via `scheduler.py`
- Also runnable manually: `python pipeline_agent.py`

### Steps (in order, autonomous)
1. Crawl The Verge for today's articles
2. Summarize each article using Claude API
3. Cluster articles into topics using TF-IDF + k-means
4. Store articles + summaries + topics in SQLite
5. Update `memory/top_of_mind.md` with top 5 findings
6. Update `memory/pipeline_session.md` with pipeline run summary
7. Generate daily HTML report with pie chart + highlights
8. On Fridays: also generate weekly HTML report
9. Send report to interface (print path + open in browser)

### Tools available
- `crawl(site, date)` — fetch articles
- `search_kb(query, ...)` — check for duplicates / prior context
- `update_memory(file, content, mode)` — write pipeline_session, top_of_mind
- `write_report(content, format, report_type, date, charts)` — generate report
- `send(target, report_path, subject, recipient)` — deliver report

### Write permissions
- `articles.db`: articles, reports tables
- `memory/pipeline_session.md`
- `memory/top_of_mind.md`

---

## Agent 2: Chat Agent

### Trigger
- Always running: `python chat_agent.py`
- Simple terminal REPL loop

### Behaviour
- Answers questions from local knowledge base first
- Falls back to web search only when user explicitly asks or KB has no answer
- Proactively mentions items from `top_of_mind.md`
- Updates `preferences.md` as it learns user interests
- Saves full conversation to `conversations` table on exit

### Tools available
- `search_kb(query, mode, topic, date_from, date_to, limit)`
- `search_history(query, date_from, date_to, limit)` — search past conversation logs
- `web_search(query, limit)`
- `update_memory(file="preferences", content, mode)`

### Write permissions
- `articles.db`: conversations table only
- `memory/preferences.md`
- `memory/chat_session.md`

---

## SQLite Schema (articles.db)

```sql
CREATE TABLE articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE,
    title         TEXT,
    published_at  TEXT,          -- ISO datetime
    crawled_at    TEXT,
    site          TEXT,          -- e.g. "theverge"
    topic         TEXT,          -- assigned by clustering
    content       TEXT,          -- cleaned full text
    summary       TEXT,          -- Claude-generated summary
    embedding     TEXT           -- JSON float array, optional future use
);

CREATE VIRTUAL TABLE articles_fts USING fts5(
    title, summary, content,
    content='articles', content_rowid='id'
);

CREATE TABLE reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type  TEXT,           -- "daily" | "weekly"
    date         TEXT,
    path         TEXT,
    created_at   TEXT
);

CREATE TABLE conversations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    ended_at     TEXT,
    summary      TEXT,           -- Claude-written 2-3 line summary of the session
    messages     TEXT            -- JSON array of {role, content} pairs
);

CREATE VIRTUAL TABLE conversations_fts USING fts5(
    summary, messages,
    content='conversations', content_rowid='id'
);
```

---

## Memory Files

### memory/pipeline_session.md
Written by pipeline agent after each run.
```
Last run: 2026-07-05 08:03
Articles crawled: 24
Topics found: AI, Hardware, Policy, Apps, Science
Report: reports/2026-07-05-daily.html
```

### memory/preferences.md
Written by chat agent as it learns user interests.
```
User interests: AI agents, Apple silicon, semiconductor policy
Preferred report format: HTML with charts
Prefers summaries over full article text
```

### memory/chat_session.md
Written by chat agent at the end of each session. A rolling summary of recent conversations — not the full log (that's in SQLite), but a human-readable digest of what was discussed, what the user seemed interested in, and any open threads. Kept to the last 7 sessions max.
```
## 2026-07-05
Topics discussed: Apple silicon M5, AI agent frameworks
User asked to go deeper on: LangGraph vs raw SDK
Open thread: user wants to revisit semiconductor policy next time

## 2026-07-04
Topics discussed: Google I/O recap, Pixel 9 hardware
Notable: user uninterested in consumer hardware stories
```

### memory/top_of_mind.md
Written by pipeline agent after clustering.
```
🔥 [Topic] One-line highlight — URL
📈 [Topic] One-line highlight — URL
⚡ [Topic] One-line highlight — URL
💡 [Topic] One-line highlight — URL
🔬 [Topic] One-line highlight — URL
```

---

## Tool Specifications

### crawl(site, date) → list[dict]
```python
# Input
site: str   # "theverge"
date: str   # "2026-07-05"

# Output
[{
    "url": str,
    "title": str,
    "published_at": str,   # ISO datetime
    "content": str,        # cleaned article text
    "summary": None        # filled downstream by Claude
}]
```
Implementation: fetch The Verge RSS feed, follow article URLs, extract main content with BeautifulSoup. Skip articles already in DB (deduplicate on URL).

---

### search_kb(query, mode, topic, date_from, date_to, limit) → list[dict]
```python
# Input
query:     str
mode:      "text" | "topic" | "date"   # default: "text"
topic:     str | None
date_from: str | None   # ISO date
date_to:   str | None   # ISO date
limit:     int          # default: 10

# Output
[{
    "url": str,
    "title": str,
    "summary": str,
    "topic": str,
    "published_at": str,
    "score": float         # FTS5 rank
}]
```
Implementation: SQLite FTS5 for text mode; WHERE clause filters for topic/date modes.

---

### search_history(query, date_from, date_to, limit) → list[dict]
```python
# Input
query:     str
date_from: str | None   # ISO date, e.g. "2026-06-28"
date_to:   str | None   # ISO date, e.g. "2026-07-05"
limit:     int          # default: 5

# Output
[{
    "started_at": str,
    "summary": str,         # Claude-written session summary
    "excerpt": str,         # most relevant snippet from messages
    "score": float          # FTS5 rank
}]
```
Implementation: FTS5 search over `conversations_fts`. Join back to `conversations` for `started_at` and `summary`. Return the top matching sessions with a short excerpt of the relevant message content.

---

### web_search(query, limit) → list[dict]
```python
# Input
query: str
limit: int   # default: 5

# Output
[{
    "url": str,
    "title": str,
    "snippet": str
}]
```
Implementation: use DuckDuckGo HTML search (no API key needed) or SerpAPI if key is available in .env.

---

### update_memory(file, content, mode) → dict
```python
# Input
file:    "pipeline_session" | "top_of_mind" | "preferences" | "chat_session"
content: str
mode:    "overwrite" | "append"   # default: "overwrite"

# Output
{"success": bool, "file": str, "written_at": str}
```
Note: enforce per-agent write permissions inside the function using a caller parameter, or rely on tool enum restriction in each agent's tool definition.

---

### write_report(content, format, report_type, date, charts) → dict
```python
# Input
content:     str              # markdown body
format:      "html" | "md"   # default: "html"
report_type: "daily" | "weekly"
date:        str | None       # defaults to today
charts: [{
    "type":  "pie" | "bar" | "timeline",
    "title": str,
    "data":  {label: value}   # e.g. {"AI": 8, "Hardware": 5}
}]

# Output
{"success": bool, "path": str, "written_at": str}
```
Implementation: for HTML, use an inline Chart.js script block for charts. For MD, render a text table instead. Save to `reports/{date}-{report_type}.html`.

---

### send(target, report_path, subject, recipient) → dict
```python
# Input
target:       "interface" | "email" | "both"
report_path:  str
subject:      str | None
recipient:    str | None

# Output
{"success": bool, "target": str, "sent_at": str, "error": str | None}
```
Implementation:
- `interface`: print the report path, open in default browser via `webbrowser.open()`
- `email`: use Gmail SMTP via `smtplib` with credentials from `.env`

---

## Core Agent Loop (core/agent_loop.py)

```python
def run_agent_loop(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    dispatch: Callable[[str, dict], any],
    on_text: Callable[[str], None] | None = None,
) -> str
```

- Calls `client.messages.create()` with model `claude-sonnet-4-6`
- On `stop_reason == "tool_use"`: calls `dispatch(tool_name, tool_input)` for each tool block, appends results, loops
- On `stop_reason == "end_turn"` or no tool calls: returns final text
- Hard ceiling: `MAX_ITERATIONS = 20`
- Errors from tools are returned to Claude as `is_error: true` tool results so Claude can reason about failures

---

## Scheduler (scheduler.py)

```python
import schedule, subprocess, time

schedule.every().day.at("08:00").do(
    lambda: subprocess.run(["python", "pipeline_agent.py"])
)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run as a background process: `python scheduler.py &`

---

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=...        # Gmail App Password, not account password
REPORT_RECIPIENT=you@gmail.com
SERPAPI_KEY=...               # optional, for web_search
```

---

## Report Format

### Daily HTML Report sections
1. Header: date, articles crawled count
2. Topic pie chart (Chart.js inline)
3. Topic clusters: list of articles per topic with title + one-line summary + URL
4. Highlights: top 3-5 most important articles with longer summary
5. Top of mind: same 5 items from top_of_mind.md

### Weekly HTML Report additions
- Trend bar chart: topic volume over 7 days
- Week in review: Claude-written narrative paragraph
- Most referenced topics / recurring themes
