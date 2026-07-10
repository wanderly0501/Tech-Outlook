"""
tools/crawler.py

The `crawl` tool exposed to the pipeline agent. Design note: this
function performs the full ingest ETL (fetch -> dedupe -> summarize ->
keyword-tag -> cluster -> store) in one call rather than exposing
separate tools for each step. REQUIREMENTS.md's tool list has no
dedicated "store"/"summarize"/"cluster" tool, and these steps are all
mechanical/deterministic — none of them need Claude's judgment, only
the steps after crawl() returns (picking top_of_mind highlights,
writing the report narrative) do. So crawl() returns articles that are
already summarized, keyword-tagged, topic-clustered, and persisted; the
pipeline agent's remaining job is to read them back via search_kb and
reason about them.

Two independent tagging mechanisms run here, in order:
  1. Per-article keywords (tools/summarize.py) — each article's own
     summarize_article() call extracts its keywords from its own
     content only, with no awareness of other articles or clustering.
  2. Topic clustering (tools/topics.py) — TF-IDF + k-means groups the
     whole batch, then labels each cluster from the pooled keywords of
     its members (step 1's output), rather than a fixed vocabulary.

Adding a new site only requires registering a crawler in
tools/crawlers/__init__.py — this function stays unchanged.
"""

from datetime import datetime

from tools.crawlers import REGISTRY
from tools import db
from tools.summarize import summarize_article
from tools.topics import cluster_topics


def crawl(site: str, date: str) -> list[dict]:
    if site not in REGISTRY:
        raise ValueError(f"Unknown site '{site}'. Available: {sorted(REGISTRY)}")

    target_date = datetime.fromisoformat(date).date()

    db.init_db()
    raw_articles = REGISTRY[site](target_date)

    existing_urls = db.get_existing_urls([a["url"] for a in raw_articles])
    new_articles = [a for a in raw_articles if a["url"] not in existing_urls]

    for article in new_articles:
        result = summarize_article(article["title"], article["content"])
        article["summary"] = result["summary"]
        article["keywords"] = result["keywords"]
        # The full body was only needed to generate the summary above —
        # neither the DB nor the agent's tool-result context should carry
        # the whole article around.
        del article["content"]

    cluster_topics(new_articles)

    for article in new_articles:
        db.insert_article(article, site=site)

    db.enforce_article_limit()

    return new_articles
