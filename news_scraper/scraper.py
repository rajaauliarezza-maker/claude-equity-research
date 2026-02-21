"""
News scraper CLI for Indonesian equity research.

Usage:
    python -m news_scraper run                   # scrape all sources
    python -m news_scraper run --push-sheets     # scrape + push to Google Sheets
    python -m news_scraper run --source kontan
    python -m news_scraper query --flagged
    python -m news_scraper query --sector Perbankan
    python -m news_scraper query --keyword akuisisi --days 14
    python -m news_scraper push                  # push DB articles to Google Sheets
    python -m news_scraper push --all            # push all articles (not just flagged)
    python -m news_scraper stats
    python -m news_scraper export
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
# Shared helper
# ---------------------------------------------------------------------------

def _push_to_sheets(articles: list[dict], push_all: bool = False, sheet_id: str = ""):
    """Push articles to Google Sheets. Prints result summary."""
    from news_scraper.notifiers.sheets import SheetsNotifier
    try:
        notifier = SheetsNotifier(sheet_id=sheet_id or None)
        if push_all:
            counts = notifier.push_all(articles)
            print(
                f"\nGoogle Sheets — Flagged tab: {counts['flagged_pushed']} new rows "
                f"(skipped {counts['flagged_skipped']})\n"
                f"               All tab:     {counts['all_pushed']} new rows "
                f"(skipped {counts['all_skipped']})"
            )
        else:
            pushed, skipped = notifier.push(articles, tab_name="Flagged", flagged_only=True)
            print(
                f"\nGoogle Sheets — Flagged tab: {pushed} new rows pushed "
                f"(skipped {skipped} duplicates)."
            )
    except Exception as exc:
        logger.error("Google Sheets push failed: %s", exc)
        print(f"\n[ERROR] Sheets push failed: {exc}")


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
    new_articles: list[dict] = []   # collect for optional Sheets push

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
            text = f"{art.title} {art.summary or ''}"
            matched = find_keywords(text)
            is_flagged = len(matched) > 0
            sector = classify_sector(art.title, art.summary or "")
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
                article_dict = {
                    "source": art.source,
                    "title": art.title,
                    "url": art.url,
                    "summary": art.summary,
                    "published_at": art.published_at,
                    "scraped_at": datetime.now().isoformat(),
                    "keywords_matched": json.dumps(matched),
                    "sector": sector,
                    "ticker": ticker,
                    "is_flagged": 1 if is_flagged else 0,
                }
                new_articles.append(article_dict)

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

    # Optional: push new articles to Google Sheets immediately after scraping
    if getattr(args, "push_sheets", False) and new_articles:
        print("\nPushing to Google Sheets...")
        _push_to_sheets(
            new_articles,
            push_all=getattr(args, "push_all", False),
            sheet_id=getattr(args, "sheet_id", "") or "",
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


def cmd_push(args):
    """Push articles from the DB to Google Sheets."""
    init_db()
    rows = query_articles(
        sector=getattr(args, "sector", None),
        source=getattr(args, "source", None),
        keyword=getattr(args, "keyword", None),
        flagged_only=not args.all,
        days=args.days,
        limit=args.limit,
    )
    if not rows:
        print("No articles to push.")
        return

    print(f"Pushing {len(rows)} articles to Google Sheets...")
    _push_to_sheets(
        rows,
        push_all=args.all,
        sheet_id=args.sheet_id or "",
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_sheets_args(p, include_all: bool = True):
    """Shared Sheets-related arguments."""
    p.add_argument(
        "--sheet-id", dest="sheet_id", default="",
        help="Google Spreadsheet ID (overrides GOOGLE_SHEET_ID env var)",
    )
    if include_all:
        p.add_argument(
            "--all", action="store_true",
            help="Push all articles (not just flagged ones)",
        )


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
    p_run.add_argument(
        "--push-sheets", action="store_true", dest="push_sheets",
        help="Push new flagged articles to Google Sheets after scraping",
    )
    p_run.add_argument(
        "--push-all", action="store_true", dest="push_all",
        help="When --push-sheets is set, push all articles (not just flagged)",
    )
    p_run.add_argument(
        "--sheet-id", dest="sheet_id", default="",
        help="Google Spreadsheet ID (overrides GOOGLE_SHEET_ID env var)",
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

    # -- push --
    p_push = sub.add_parser("push", help="Push articles from DB to Google Sheets")
    p_push.add_argument("--sector", help="Filter by sector")
    p_push.add_argument("--source", help="Filter by source")
    p_push.add_argument("--keyword", help="Filter by keyword")
    p_push.add_argument("--all", action="store_true", help="Push all articles, not just flagged")
    p_push.add_argument("--days", type=int, default=7, help="Look back N days (default 7)")
    p_push.add_argument("--limit", type=int, default=1000, help="Max rows to push (default 1000)")
    _add_sheets_args(p_push, include_all=False)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    {
        "run": cmd_run,
        "query": cmd_query,
        "stats": cmd_stats,
        "export": cmd_export,
        "push": cmd_push,
    }[args.command](args)


if __name__ == "__main__":
    main()
