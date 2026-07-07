"""
tools/search_kb.py

SQLite FTS5 search over the local article knowledge base.
"""

from tools import db


def _row_to_dict(row) -> dict:
    return {
        "url": row["url"],
        "title": row["title"],
        "summary": row["summary"],
        "topic": row["topic"],
        "published_at": row["published_at"],
        "score": row["score"] if "score" in row.keys() else 0.0,
    }


def search_kb(
    query: str,
    mode: str = "text",
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> list[dict]:
    db.init_db()
    conn = db.get_connection()
    try:
        if mode == "topic":
            sql = """
                SELECT url, title, summary, topic, published_at, 0.0 AS score
                FROM articles
                WHERE topic = ?
                ORDER BY published_at DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (topic, limit)).fetchall()

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
                SELECT url, title, summary, topic, published_at, 0.0 AS score
                FROM articles
                {where}
                ORDER BY published_at DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (*params, limit)).fetchall()

        else:  # mode == "text"
            sql = """
                SELECT a.url, a.title, a.summary, a.topic, a.published_at,
                       bm25(articles_fts) AS score
                FROM articles_fts
                JOIN articles a ON a.id = articles_fts.rowid
                WHERE articles_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """
            rows = conn.execute(sql, (query, limit)).fetchall()

        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()
