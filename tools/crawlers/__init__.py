"""
tools/crawlers/

Site-specific crawler plugins live here, one module per site, each
exposing a `crawl(target_date) -> list[dict]` function. `REGISTRY`
maps a site key (as passed to the `crawl(site, date)` tool) to that
function, so adding support for a new website is just:

    1. Write tools/crawlers/newsite.py with a `crawl(target_date)` function.
    2. Register it below.

Everything else (dedup, summarization, clustering, storage) in
tools/crawler.py is site-agnostic and needs no changes.
"""

from tools.crawlers import theverge

REGISTRY = {
    "theverge": theverge.crawl,
}
