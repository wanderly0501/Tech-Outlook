"""
tools/crawler.py

The `crawl` tool exposed to the pipeline agent. Design note: this
function performs the full ingest ETL (fetch -> dedupe -> summarize ->
cluster -> store) in one call rather than exposing separate tools for
each step. REQUIREMENTS.md's tool list has no dedicated "store" or
"summarize" tool, and steps 1-4 of the pipeline (crawl, summarize,
cluster, store) are all mechanical/deterministic — none of them need
Claude's judgment, only steps 4 onward (picking top_of_mind highlights,
writing the report narrative) do. So crawl() returns articles that are
already summarized, topic-labeled, and persisted; the pipeline agent's
remaining job is to read them back via search_kb and reason about them.

Adding a new site only requires registering a crawler in
tools/crawlers/__init__.py — this function stays unchanged.
"""

from datetime import datetime

from tools.crawlers import REGISTRY
from tools import db
from tools.summarize import summarize_article
from tools.topics import assign_topics


def crawl(site: str, date: str) -> list[dict]:
    if site not in REGISTRY:
        raise ValueError(f"Unknown site '{site}'. Available: {sorted(REGISTRY)}")

    target_date = datetime.fromisoformat(date).date()

    db.init_db()
    raw_articles = REGISTRY[site](target_date)

    existing_urls = db.get_existing_urls([a["url"] for a in raw_articles])
    new_articles = [a for a in raw_articles if a["url"] not in existing_urls]

    for article in new_articles:
        article["summary"] = summarize_article(article["title"], article["content"])
        # The full body was only needed to generate the summary above —
        # neither the DB nor the agent's tool-result context should carry
        # the whole article around.
        del article["content"]

    assign_topics(new_articles)

    for article in new_articles:
        db.insert_article(article, site=site)

    return new_articles
