"""
tools/search_history.py

FTS5 search over past chat sessions, for the chat agent's
"didn't we talk about..." recall.
"""

import re

from tools import db

_SNIPPET_RADIUS = 160


def _excerpt(messages_text: str, query: str) -> str:
    if not query:
        return messages_text[:_SNIPPET_RADIUS]
    match = re.search(re.escape(query), messages_text, re.IGNORECASE)
    if not match:
        return messages_text[:_SNIPPET_RADIUS]
    start = max(0, match.start() - _SNIPPET_RADIUS // 2)
    end = min(len(messages_text), match.end() + _SNIPPET_RADIUS // 2)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(messages_text) else ""
    return f"{prefix}{messages_text[start:end]}{suffix}"


def search_history(
    query: str,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 5,
) -> list[dict]:
    db.init_db()
    conn = db.get_connection()
    try:
        conditions = ["conversations_fts MATCH ?"]
        params: list = [query]
        if date_from:
            conditions.append("c.started_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("c.started_at <= ?")
            params.append(date_to)

        sql = f"""
            SELECT c.started_at, c.summary, c.messages, bm25(conversations_fts) AS score
            FROM conversations_fts
            JOIN conversations c ON c.id = conversations_fts.rowid
            WHERE {' AND '.join(conditions)}
            ORDER BY score
            LIMIT ?
        """
        rows = conn.execute(sql, (*params, limit)).fetchall()

        return [
            {
                "started_at": row["started_at"],
                "summary": row["summary"],
                "excerpt": _excerpt(row["messages"] or "", query),
                "score": row["score"],
            }
            for row in rows
        ]
    finally:
        conn.close()
