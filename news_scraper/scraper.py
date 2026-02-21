"""
News scraper CLI for Indonesian equity research.

Usage:
    python -m news_scraper.scraper run          # scrape all sources
    python -m news_scraper.scraper run --source kontan
    python -m news_scraper.scraper query        # show recent flagged articles
    python -m news_scraper.scraper query --sector Perbankan
    python -m news_scraper.scraper query --keyword akuisisi --days 14
    python -m news_scraper.scraper stats        # show DB statistics
    python -m news_scraper.scraper export       # export flagged articles to CSV
"""

import argparse
import csv
import json
import logging
import sys
import os
from datetime import datetime

# Allow running as a standalone script from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from news_scraper.database import init_db, upsert_article, log_scrape, query_articles, get_stats
from news_scraper.classifier import find_keywords, classify_sector, extract_ticker
from news_scraper.scrapers import ALL_SCRAPERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("news_scraper")

SCRAPER_MAP = {s.source_id: s for s in ALL_SCRAPERS}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run(args):
    """Fetch articles from one or all sources, classify, and store."""
    init_db()

    sources_to_run = ALL_SCRAPERS
    if args.source:
        key = args.source.lower()
        if key not in SCRAPER_MAP:
            print(f"Unknown source '{args.source}'. Available: {', '.join(SCRAPER_MAP)}")
            sys.exit(1)
        sources_to_run = [SCRAPER_MAP[key]]

    total_new = 0
    total_flagged = 0

    for ScraperClass in sources_to_run:
        scraper = ScraperClass(
            timeout=args.timeout,
            max_articles=args.max_articles,
        )
        logger.info("=== Scraping: %s ===", scraper.name)
        error_msg = None
        articles = []

        try:
            articles = scraper.fetch_articles()
        except Exception as exc:
            error_msg = str(exc)
            logger.error("[%s] Scraper failed: %s", scraper.source_id, exc)

        found = len(articles)
        new_count = 0
        flagged_count = 0

        for art in articles:
            # Combine title + summary for classification
            text = f"{art.title} {art.summary or ''}"

            # Keyword filtering
            matched = find_keywords(text)
            is_flagged = len(matched) > 0

            # Sector classification
            sector = classify_sector(art.title, art.summary or "")

            # Ticker extraction
            ticker = extract_ticker(art.title, art.summary or "")

            is_new, _aid = upsert_article(
                source=art.source,
                title=art.title,
                url=art.url,
                summary=art.summary,
                published_at=art.published_at,
                keywords_matched=matched,
                sector=sector,
                ticker=ticker,
                is_flagged=is_flagged,
            )

            if is_new:
                new_count += 1
                if is_flagged:
                    flagged_count += 1
                    kw_str = ", ".join(matched)
                    sec_str = sector or "—"
                    tick_str = f" [{ticker}]" if ticker else ""
                    print(
                        f"  [FLAG] {art.source}{tick_str} | {sec_str} | {kw_str}\n"
                        f"         {art.title}\n"
                        f"         {art.url}\n"
                    )

        log_scrape(
            source=scraper.source_id,
            articles_found=found,
            articles_new=new_count,
            articles_flagged=flagged_count,
            error=error_msg,
        )

        logger.info(
            "[%s] done — found=%d  new=%d  flagged=%d",
            scraper.source_id, found, new_count, flagged_count,
        )
        total_new += new_count
        total_flagged += flagged_count

    print(
        f"\nSummary: {total_new} new articles stored, "
        f"{total_flagged} flagged for corporate action keywords."
    )


def cmd_query(args):
    """Query articles from the database."""
    init_db()
    rows = query_articles(
        sector=args.sector,
        source=args.source,
        keyword=args.keyword,
        flagged_only=args.flagged,
        days=args.days,
        limit=args.limit,
    )
    if not rows:
        print("No articles found matching the criteria.")
        return

    print(f"{'#':<4} {'Source':<20} {'Sector':<22} {'Published':<12} Title")
    print("-" * 100)
    for i, r in enumerate(rows, 1):
        pub = (r.get("published_at") or r.get("scraped_at") or "")[:10]
        sector = (r.get("sector") or "—")[:20]
        source = (r.get("source") or "")[:18]
        title = r.get("title", "")
        kws = json.loads(r.get("keywords_matched") or "[]")
        flag = "[F] " if r.get("is_flagged") else "    "
        ticker = f"[{r['ticker']}] " if r.get("ticker") else ""
        print(f"{i:<4} {flag}{source:<18} {sector:<22} {pub:<12} {ticker}{title}")
        if kws and args.verbose:
            print(f"          Keywords: {', '.join(kws)}")
            print(f"          URL: {r.get('url', '')}")
    print(f"\n{len(rows)} article(s) returned.")


def cmd_stats(args):
    """Print database statistics."""
    init_db()
    s = get_stats()
    print(f"\n=== News Scraper Database Stats ===")
    print(f"Total articles : {s['total']}")
    print(f"Flagged        : {s['flagged']}")

    print("\nBy source:")
    for row in s["by_source"]:
        print(f"  {row['source']:<25} {row['n']:>5}")

    print("\nBy sector:")
    for row in s["by_sector"]:
        print(f"  {row['sector']:<28} {row['n']:>5}")

    if s["last_scrapes"]:
        print("\nRecent scrape runs:")
        for row in s["last_scrapes"]:
            print(
                f"  {row['run_at'][:19]}  {row['source']:<15} "
                f"new={row['articles_new']}  flagged={row['articles_flagged']}"
            )


def cmd_export(args):
    """Export flagged articles to CSV."""
    init_db()
    rows = query_articles(
        sector=args.sector,
        source=args.source,
        keyword=args.keyword,
        flagged_only=not args.all,
        days=args.days,
        limit=args.limit,
    )
    out_path = args.output or f"news_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "id", "source", "sector", "ticker", "title", "summary",
            "url", "published_at", "scraped_at", "keywords_matched", "is_flagged",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Exported {len(rows)} articles to {out_path}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Indonesian equity news scraper with keyword filtering and sector tagging."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- run --
    p_run = sub.add_parser("run", help="Scrape news from all (or one) source(s)")
    p_run.add_argument(
        "--source", metavar="SOURCE",
        help=f"Scrape only this source. Choices: {', '.join(SCRAPER_MAP.keys())}",
    )
    p_run.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    p_run.add_argument(
        "--max-articles", type=int, default=50, dest="max_articles",
        help="Max articles per source per run",
    )

    # -- query --
    p_q = sub.add_parser("query", help="Query stored articles")
    p_q.add_argument("--sector", help="Filter by sector (partial match)")
    p_q.add_argument("--source", help="Filter by source name (partial match)")
    p_q.add_argument("--keyword", help="Filter by keyword in title/summary")
    p_q.add_argument("--flagged", action="store_true", help="Show only flagged articles")
    p_q.add_argument("--days", type=int, default=7, help="Look back N days (default 7)")
    p_q.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    p_q.add_argument("-v", "--verbose", action="store_true", help="Show keywords and URL")

    # -- stats --
    sub.add_parser("stats", help="Show database statistics")

    # -- export --
    p_ex = sub.add_parser("export", help="Export articles to CSV")
    p_ex.add_argument("--output", "-o", help="Output CSV path")
    p_ex.add_argument("--sector", help="Filter by sector")
    p_ex.add_argument("--source", help="Filter by source")
    p_ex.add_argument("--keyword", help="Filter by keyword")
    p_ex.add_argument("--all", action="store_true", help="Export all articles, not just flagged")
    p_ex.add_argument("--days", type=int, default=30, help="Look back N days (default 30)")
    p_ex.add_argument("--limit", type=int, default=1000, help="Max results (default 1000)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    {
        "run": cmd_run,
        "query": cmd_query,
        "stats": cmd_stats,
        "export": cmd_export,
    }[args.command](args)


if __name__ == "__main__":
    main()
