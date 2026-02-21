"""
SQLite database layer for news scraper.
Stores articles with keyword matches, sector flags, and metadata.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.environ.get("NEWS_DB_PATH", os.path.join(os.path.dirname(__file__), "news.db"))


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create tables if they don't exist."""
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source          TEXT    NOT NULL,
                title           TEXT    NOT NULL,
                summary         TEXT,
                url             TEXT    UNIQUE NOT NULL,
                published_at    TEXT,
                scraped_at      TEXT    DEFAULT (datetime('now')),
                keywords_matched TEXT,
                sector          TEXT,
                ticker          TEXT,
                is_flagged      INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_articles_source      ON articles(source);
            CREATE INDEX IF NOT EXISTS idx_articles_sector      ON articles(sector);
            CREATE INDEX IF NOT EXISTS idx_articles_published   ON articles(published_at);
            CREATE INDEX IF NOT EXISTS idx_articles_is_flagged  ON articles(is_flagged);
            CREATE INDEX IF NOT EXISTS idx_articles_scraped_at  ON articles(scraped_at);

            CREATE TABLE IF NOT EXISTS scrape_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT    NOT NULL,
                run_at      TEXT    DEFAULT (datetime('now')),
                articles_found    INTEGER DEFAULT 0,
                articles_new      INTEGER DEFAULT 0,
                articles_flagged  INTEGER DEFAULT 0,
                error       TEXT
            );
        """)


def upsert_article(
    source: str,
    title: str,
    url: str,
    summary: Optional[str] = None,
    published_at: Optional[str] = None,
    keywords_matched: Optional[list] = None,
    sector: Optional[str] = None,
    ticker: Optional[str] = None,
    is_flagged: bool = False,
    db_path: str = DB_PATH,
) -> tuple[bool, int]:
    """
    Insert or skip article (URL is unique key).
    Returns (is_new, article_id).
    """
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT id FROM articles WHERE url = ?", (url,))
        existing = cur.fetchone()
        if existing:
            return False, existing["id"]

        cur = conn.execute(
            """
            INSERT INTO articles
                (source, title, summary, url, published_at, keywords_matched,
                 sector, ticker, is_flagged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                title,
                summary,
                url,
                published_at,
                json.dumps(keywords_matched or []),
                sector,
                ticker,
                1 if is_flagged else 0,
            ),
        )
        return True, cur.lastrowid


def log_scrape(
    source: str,
    articles_found: int,
    articles_new: int,
    articles_flagged: int,
    error: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO scrape_log
                (source, articles_found, articles_new, articles_flagged, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, articles_found, articles_new, articles_flagged, error),
        )


def query_articles(
    sector: Optional[str] = None,
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    flagged_only: bool = False,
    days: int = 7,
    limit: int = 100,
    db_path: str = DB_PATH,
) -> list[dict]:
    """Flexible query with optional filters."""
    conditions = [
        "scraped_at >= datetime('now', ?)"
    ]
    params: list = [f"-{days} days"]

    if sector:
        conditions.append("LOWER(sector) LIKE ?")
        params.append(f"%{sector.lower()}%")
    if source:
        conditions.append("LOWER(source) LIKE ?")
        params.append(f"%{source.lower()}%")
    if keyword:
        conditions.append(
            "(LOWER(title) LIKE ? OR LOWER(summary) LIKE ? OR LOWER(keywords_matched) LIKE ?)"
        )
        kw = f"%{keyword.lower()}%"
        params.extend([kw, kw, kw])
    if flagged_only:
        conditions.append("is_flagged = 1")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT * FROM articles
        WHERE {where}
        ORDER BY scraped_at DESC
        LIMIT ?
    """
    params.append(limit)

    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_stats(db_path: str = DB_PATH) -> dict:
    with get_connection(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        flagged = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE is_flagged = 1"
        ).fetchone()[0]
        by_source = conn.execute(
            "SELECT source, COUNT(*) as n FROM articles GROUP BY source ORDER BY n DESC"
        ).fetchall()
        by_sector = conn.execute(
            "SELECT sector, COUNT(*) as n FROM articles WHERE sector IS NOT NULL "
            "GROUP BY sector ORDER BY n DESC"
        ).fetchall()
        last_scrape = conn.execute(
            "SELECT source, run_at, articles_new, articles_flagged "
            "FROM scrape_log ORDER BY run_at DESC LIMIT 10"
        ).fetchall()
        return {
            "total": total,
            "flagged": flagged,
            "by_source": [dict(r) for r in by_source],
            "by_sector": [dict(r) for r in by_sector],
            "last_scrapes": [dict(r) for r in last_scrape],
        }
