# Tech Lookout

A local Python agent system that crawls tech news daily, maintains a knowledge
base, generates reports, and lets you chat with it about tech trends — all
without hitting the internet during chat.

Two agents, two processes, zero shared state conflicts. Full spec in
[REQUIREMENTS.md](REQUIREMENTS.md); this file is the practical "what is this
and how do I run it" overview.

---

## The Two Agents

### Pipeline Agent (`pipeline_agent.py`)

Runs once a day (or on demand). No user present — it crawls, summarizes,
clusters, stores, and reports autonomously.

1. Crawl the configured site for new articles (dedup against the DB)
2. Summarize each new article via Claude
3. Cluster into topics (TF-IDF + k-means, labeled against a fixed vocabulary)
4. Store each article's summary (under 100 words) + topic in SQLite — the
   full article text is discarded once it's been summarized
5. Pick the day's 5 most interesting findings into `memory/top_of_mind.md`
6. Write a run summary to `memory/session.md`
7. Generate a daily HTML report (topic pie chart + highlights); weekly too on Fridays
8. Surface the report (open locally, and/or email)

### Chat Agent (`chat_agent.py`)

Always-on. Answers from the local knowledge base first, falls back to web
search only when asked or when the KB comes up empty. Learns your interests
over time and remembers past conversations. Three front ends share the same
agent loop and tools:

- **Terminal REPL** — `python chat_agent.py`
- **Web UI** — `python webui/app.py`, a thin Flask wrapper around the same
  `chat_agent.py` building blocks (see [webui/README.md](webui/README.md))
- **Desktop app** — `python desktop/app.py`, a system-tray app that hosts the
  web UI in a native window and also runs the daily pipeline in the
  background, so no separate `scheduler.py` process is needed (see
  [desktop/README.md](desktop/README.md))

---

## Project Structure

```
core/
  agent_loop.py           # shared ReAct loop (Claude tool-calling) used by both agents
tools/
  db.py                   # SQLite schema + connection + insert/query helpers
  config.py               # shared paths, memory write-permission table
  crawler.py              # crawl(site, date) tool: dedupe -> summarize -> cluster -> store
  crawlers/
    base_crawler.py        # generic threaded BFS crawler (site-agnostic)
    theverge.py             # The Verge plugin: date/content extraction, article-URL matching
  summarize.py            # Claude call to summarize one article
  topics.py                # TF-IDF + k-means clustering, keyword-based topic labeling
  search_kb.py             # SQLite FTS5 search over articles
  search_history.py        # SQLite FTS5 search over past conversations
  web_search.py             # DuckDuckGo (or SerpAPI) on-demand web search
  update_memory.py          # writes memory/*.md, enforces per-agent permissions
  write_report.py           # HTML (inline Chart.js) / Markdown report rendering
  send.py                    # opens report locally and/or emails it
memory/
  session.md               # pipeline: last run stats
  top_of_mind.md            # pipeline: interesting things/trends found recently
  preferences.md            # chat: learned user interests
  user_history.md            # chat: rolling digest of recent sessions (last 7)
knowledge/
  articles.db               # SQLite DB (article summaries, reports, conversations + FTS5) — no full article text
reports/                    # generated HTML/MD reports
prompts/
  pipeline_agent.md          # pipeline agent system prompt
  chat_agent.md               # chat agent system prompt
webui/
  app.py                     # Flask wrapper around chat_agent.py's TOOLS/dispatch/prompt
  templates/index.html        # chat page + sidebar (top of mind, reports)
  static/{style.css,app.js}    # no build step, vanilla JS
  requirements.txt              # just flask, kept separate from the root deps
desktop/
  app.py                     # tray app: native window over webui/app.py + background scheduler
  requirements.txt            # pywebview, pystray, pillow
pipeline_agent.py
chat_agent.py
scheduler.py                 # triggers pipeline_agent.py daily at 00:01
requirements.txt
.env.example
```

---

## Adding a New Crawler Site

The crawler is built to support more than The Verge without touching the
pipeline agent or its tool schema:

1. Add `tools/crawlers/<site>.py` exposing a `crawl(target_date) -> list[dict]`
   function. Reuse the generic `WebCrawler` in `base_crawler.py` — supply your
   own `is_article_url` and `date_extractor` callables (see `theverge.py` for
   the pattern).
2. Register it in `tools/crawlers/__init__.py`'s `REGISTRY` dict.
3. Add the new site key to the `"site"` enum in the `crawl` tool schema in
   `pipeline_agent.py`.

`tools/crawler.py` (dedup, summarize, cluster, store) and everything
downstream needs no changes.

---

## Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# Set up .env
cp .env.example .env
# add your ANTHROPIC_API_KEY (and Gmail/SerpAPI keys if you want email/web search)

# Run the pipeline manually (first time, or any time)
python pipeline_agent.py

# Start the scheduler (background) — triggers pipeline_agent.py daily at 00:01
python scheduler.py &

# Start the chat agent — terminal REPL...
python chat_agent.py

# ...or the web UI instead
pip install -r webui/requirements.txt
python webui/app.py   # open http://127.0.0.1:5000

# ...or the desktop app (bundles the web UI + scheduler into one tray app)
pip install -r desktop/requirements.txt
python desktop/app.py
```

Knowledge base, memory files, and reports are created on first run — nothing
to set up by hand beyond the `.env`.

---

## Design Notes

- **Read permissions are open, write permissions are enforced.** Both agents
  can read the whole DB and all memory files, but `update_memory` checks a
  `caller` argument against `tools/config.py`'s permission table (pipeline:
  `session`, `top_of_mind`; chat: `preferences`, `user_history`) in addition
  to each agent's own tool-schema enum restricting which files it can even
  ask to write.
- **Crawl does the mechanical ETL in one call.** Summarizing and clustering
  aren't judgment calls, so `crawl()` handles fetch → dedupe → summarize →
  cluster → store internally and returns already-processed articles. The
  agent loop is reserved for steps that need Claude's judgment: picking
  top-of-mind highlights and writing the report narrative.
- **Only the summary is kept, not the article body.** `crawl()` fetches full
  article text just long enough to generate an under-100-word summary, then
  discards it (`tools/crawler.py`) — the DB has no `content` column. The KB
  is for search and recall, not for mirroring the source site.
- **Topic clustering degrades gracefully.** If scikit-learn's compiled
  clustering extension can't load in a given environment, topic assignment
  falls back to keyword-only labeling instead of failing the crawl step.
- **The web UI is a pure add-on.** `webui/app.py` imports `chat_agent.py`'s
  module-level `TOOLS`, `dispatch`, prompt, and `save_conversation` rather
  than reimplementing them, so the REPL and the web UI can never drift apart.
  It holds one shared in-memory conversation (same one-session model as the
  REPL) — fine for a single-user local tool, not meant for concurrent users.
- **The desktop app is a shell around the other two, not a third
  implementation.** `desktop/app.py` imports `webui.app`'s Flask instance
  directly (runs it in a background thread, points a `pywebview` window at
  it) and imports `pipeline_agent.run_pipeline` for its background scheduler
  and "Run Pipeline Now" tray action — same `schedule`-at-00:01-for-yesterday
  logic as `scheduler.py`, just embedded in the app process instead of a
  separate script. Closing the window hides it rather than quitting; only
  the tray's "Quit" stops the scheduler and exits.
