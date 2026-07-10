"""
tools/search_kb.py

SQLite FTS5 search over the local article knowledge base.
"""

import re

from tools import db

# FTS5's default MATCH is an implicit AND over every bareword, with no
# stemming — a natural-language question like "what did you find about
# GTA 6 preorders" almost never matches a stored title/summary verbatim,
# even when a clearly relevant article exists. _build_fts_query rewrites
# the raw query into an OR-of-terms prefix search instead, trading a
# little precision for much better recall on conversational input; bm25
# ranking still puts the closest match first.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "i", "you", "your", "me",
    "my", "it", "its", "this", "that", "what", "when", "where", "who",
    "which", "how", "why", "and", "or", "of", "in", "on", "for", "to",
    "from", "about", "with", "as", "at", "by", "any", "some", "there",
}


def _build_fts_query(raw_query: str) -> str:
    tokens = re.findall(r"\w+", raw_query.lower())
    terms = [t for t in tokens if t not in _STOPWORDS] or tokens
    if not terms:
        return '""'  # empty/whitespace-only query — match nothing
    return " OR ".join(f'"{t}"*' if len(t) >= 4 else f'"{t}"' for t in terms)


def _row_to_dict(row) -> dict:
    return {
        "url": row["url"],
        "title": row["title"],
        "summary": row["summary"],
        "topic": row["topic"],
        "keywords": row["keywords"],
        "published_at": row["published_at"],
        "score": row["score"] if "score" in row.keys() else 0.0,
    }


def search_kb(
    query: str,
    mode: str = "text",
    topic: str | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> list[dict]:
    db.init_db()
    conn = db.get_connection()
    try:
        if mode == "topic":
            # Exact match against the clustering-assigned topic (tools/topics.py).
            sql = """
                SELECT url, title, summary, topic, keywords, published_at, 0.0 AS score
                FROM articles
                WHERE topic = ?
                ORDER BY published_at DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (topic, limit)).fetchall()

        elif mode == "keyword":
            # Substring match against the per-article keyword list
            # (tools/summarize.py) — a different, finer-grained axis than topic.
            sql = """
                SELECT url, title, summary, topic, keywords, published_at, 0.0 AS score
                FROM articles
                WHERE keywords LIKE ?
                ORDER BY published_at DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (f"%{(keyword or '').lower()}%", limit)).fetchall()

        elif mode == "date":
            conditions = []
            params: list = []
            if date_from:
                conditions.append("published_at >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("published_at <= ?")
                params.append(date_to)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT url, title, summary, topic, keywords, published_at, 0.0 AS score
                FROM articles
                {where}
                ORDER BY published_at DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (*params, limit)).fetchall()

        else:  # mode == "text"
            sql = """
                SELECT a.url, a.title, a.summary, a.topic, a.keywords, a.published_at,
                       bm25(articles_fts) AS score
                FROM articles_fts
                JOIN articles a ON a.id = articles_fts.rowid
                WHERE articles_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """
            rows = conn.execute(sql, (_build_fts_query(query), limit)).fetchall()

        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()
