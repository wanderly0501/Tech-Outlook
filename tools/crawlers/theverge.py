"""
tools/crawlers/theverge.py

Site plugin for The Verge, built on the generic WebCrawler in
base_crawler.py. Supplies the three things that are specific to this
site: how to recognize an article URL, how to read its publish date,
and how to pull out a clean title + body.
"""

import re
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup

from tools.crawlers.base_crawler import WebCrawler

START_URLS = ["https://www.theverge.com/"]
ALLOWED_DOMAINS = ["theverge.com"]

# Article URLs look like /<section>/<numeric-id>/<slug>, e.g.
# https://www.theverge.com/entertainment/960958/flatbush-zombies-...
# Listing, tag, and author pages don't have that numeric-id segment.
_ARTICLE_PATH_RE = re.compile(r"^/[^/]+/\d+/[^/]+$")


def is_article_url(url: str) -> bool:
    from urllib.parse import urlparse

    path = urlparse(url).path or "/"
    return bool(_ARTICLE_PATH_RE.match(path))


def extract_date(html_content: str) -> Optional[date]:
    soup = BeautifulSoup(html_content, "html.parser")

    time_tag = soup.find("time", class_="c-byline__item c-byline__item--date")
    if time_tag and "datetime" in time_tag.attrs:
        try:
            return datetime.fromisoformat(time_tag["datetime"]).date()
        except ValueError:
            pass

    meta_tag = soup.find("meta", property="article:published_time")
    if meta_tag and "content" in meta_tag.attrs:
        try:
            return datetime.fromisoformat(meta_tag["content"]).date()
        except ValueError:
            pass

    return None


def extract_content(html_content: str) -> dict:
    """Pull a title and cleaned body text out of an article page."""
    soup = BeautifulSoup(html_content, "html.parser")

    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        meta_title = soup.find("meta", property="og:title")
        if meta_title and "content" in meta_title.attrs:
            title = meta_title["content"]

    article_tag = soup.find("article") or soup

    paragraphs = [
        p.get_text(" ", strip=True)
        for p in article_tag.find_all("p")
    ]
    # Drop boilerplate/short fragments (nav labels, share prompts, etc.)
    paragraphs = [p for p in paragraphs if len(p) > 40]
    content = "\n\n".join(paragraphs)

    return {"title": title, "content": content}


def crawl(target_date: date, max_num: int = 500) -> list[dict]:
    """Crawl The Verge for articles published on or after target_date."""
    crawler = WebCrawler(
        start_urls=START_URLS,
        allowed_domains=ALLOWED_DOMAINS,
        max_depth=2,
        max_num=max_num,
        filter_date=target_date,
        is_article_url=is_article_url,
        date_extractor=extract_date,
    )
    results = crawler.crawl()

    articles = []
    for result in results:
        if not result.html_content:
            continue
        parsed = extract_content(result.html_content)
        if not parsed["title"] or not parsed["content"]:
            continue
        published_at = extract_date(result.html_content)
        articles.append({
            "url": result.url,
            "title": parsed["title"],
            "published_at": published_at.isoformat() if published_at else None,
            "content": parsed["content"],
            "summary": None,
        })
    return articles
