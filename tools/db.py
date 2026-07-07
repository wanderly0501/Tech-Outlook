"""
tools/db.py

Single source of truth for the SQLite schema (articles.db) and the
low-level helpers every tool needs. FTS5 tables are kept in sync with
their content tables via triggers, so callers never write to the FTS
tables directly.
"""

import json
import sqlite3
from datetime import datetime, timezone

from tools.config import DB_PATH, MAX_ARTICLES

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE,
    title         TEXT,
    published_at  TEXT,
    crawled_at    TEXT,
    site          TEXT,
    topic         TEXT,
    summary       TEXT,
    embedding     TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, summary,
    content='articles', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary)
    VALUES (new.id, new.title, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary)
    VALUES ('delete', old.id, old.title, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary)
    VALUES ('delete', old.id, old.title, old.summary);
    INSERT INTO articles_fts(rowid, title, summary)
    VALUES (new.id, new.title, new.summary);
END;

CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type  TEXT,
    date         TEXT,
    path         TEXT,
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    ended_at     TEXT,
    summary      TEXT,
    messages     TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
    summary, messages,
    content='conversations', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations BEGIN
    INSERT INTO conversations_fts(rowid, summary, messages)
    VALUES (new.id, new.summary, new.messages);
END;

CREATE TRIGGER IF NOT EXISTS conversations_ad AFTER DELETE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, summary, messages)
    VALUES ('delete', old.id, old.summary, old.messages);
END;

CREATE TRIGGER IF NOT EXISTS conversations_au AFTER UPDATE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, summary, messages)
    VALUES ('delete', old.id, old.summary, old.messages);
    INSERT INTO conversations_fts(rowid, summary, messages)
    VALUES (new.id, new.summary, new.messages);
END;
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_existing_urls(urls: list[str]) -> set[str]:
    """Return the subset of `urls` already present in the articles table."""
    if not urls:
        return set()
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in urls)
        rows = conn.execute(
            f"SELECT url FROM articles WHERE url IN ({placeholders})", urls
        ).fetchall()
        return {row["url"] for row in rows}
    finally:
        conn.close()


def insert_article(article: dict, site: str) -> int:
    """
    Insert a new article. Assumes caller already deduped on URL.
    Only the summary is persisted, not the full article body — the KB is
    meant for search and recall, not for storing a copy of the source text.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO articles
                (url, title, published_at, crawled_at, site, topic, summary, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
            """,
            (
                article["url"],
                article.get("title"),
                article.get("published_at"),
                datetime.now(timezone.utc).isoformat(),
                site,
                article.get("topic"),
                article.get("summary"),
                json.dumps(article["embedding"]) if article.get("embedding") else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def enforce_article_limit(max_items: int = MAX_ARTICLES) -> int:
    """
    Delete the oldest articles (by crawled_at) once the table exceeds
    max_items. Returns the number of rows deleted. The articles_ad
    trigger keeps articles_fts in sync automatically.
    """
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        overflow = count - max_items
        if overflow <= 0:
            return 0
        conn.execute(
            """
            DELETE FROM articles
            WHERE id IN (SELECT id FROM articles ORDER BY crawled_at ASC LIMIT ?)
            """,
            (overflow,),
        )
        conn.commit()
        return overflow
    finally:
        conn.close()


def insert_report(report_type: str, date: str, path: str) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO reports (report_type, date, path, created_at) VALUES (?, ?, ?, ?)",
            (report_type, date, path, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_conversation(started_at: str, ended_at: str, summary: str, messages: list) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO conversations (started_at, ended_at, summary, messages)
            VALUES (?, ?, ?, ?)
            """,
            (started_at, ended_at, summary, json.dumps(messages)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
