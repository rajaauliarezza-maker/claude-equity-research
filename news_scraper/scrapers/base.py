"""
Base scraper class providing shared HTTP, RSS, and HTML-parsing utilities.
"""
import time
import logging
import random
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Rotate user agents to reduce blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


@dataclass
class Article:
    source: str
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[str] = None  # ISO-8601 string or None
    keywords_matched: list = field(default_factory=list)
    sector: Optional[str] = None
    ticker: Optional[str] = None
    is_flagged: bool = False


class BaseScraper:
    """
    Base class for all news source scrapers.

    Subclasses must implement `fetch_articles()` and set:
        name: str         - human-readable source name
        source_id: str    - short identifier used in DB
    """

    name: str = "Unknown"
    source_id: str = "unknown"
    request_delay: float = 1.5   # seconds between requests

    def __init__(self, timeout: int = 20, max_articles: int = 50):
        self.timeout = timeout
        self.max_articles = max_articles
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """GET with retry logic and random User-Agent rotation."""
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", random.choice(USER_AGENTS))
        for attempt in range(3):
            try:
                resp = self.session.get(
                    url, headers=headers, timeout=self.timeout, **kwargs
                )
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                wait = 2 ** attempt
                logger.warning(
                    "[%s] GET %s failed (attempt %d): %s – retrying in %ds",
                    self.source_id, url, attempt + 1, exc, wait,
                )
                time.sleep(wait)
        logger.error("[%s] Failed to fetch %s after 3 attempts", self.source_id, url)
        return None

    def _soup(self, url: str, **kwargs) -> Optional[BeautifulSoup]:
        resp = self._get(url, **kwargs)
        if resp is None:
            return None
        return BeautifulSoup(resp.content, "lxml")

    # ------------------------------------------------------------------
    # RSS helper
    # ------------------------------------------------------------------

    def _parse_rss(self, rss_url: str) -> list[dict]:
        """
        Parse an RSS/Atom feed and return a list of dicts with keys:
            title, url, summary, published_at
        Falls back to html.parser via feedparser if available,
        otherwise uses requests + BeautifulSoup.
        """
        try:
            import feedparser  # optional but preferred
            feed = feedparser.parse(rss_url)
            articles = []
            for entry in feed.entries[: self.max_articles]:
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                articles.append(
                    {
                        "title": entry.get("title", "").strip(),
                        "url": entry.get("link", "").strip(),
                        "summary": BeautifulSoup(
                            entry.get("summary", ""), "lxml"
                        ).get_text(separator=" ", strip=True),
                        "published_at": pub,
                    }
                )
            return articles
        except ImportError:
            pass

        # Fallback: manual XML parse via BeautifulSoup
        resp = self._get(rss_url)
        if resp is None:
            return []
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item")[: self.max_articles]
        articles = []
        for item in items:
            title = (item.find("title") or item.find("title")).get_text(strip=True)
            link = (item.find("link") or item.find("guid") or {}).get_text(strip=True) if item.find("link") else ""
            desc_tag = item.find("description")
            summary = ""
            if desc_tag:
                summary = BeautifulSoup(desc_tag.get_text(), "lxml").get_text(
                    separator=" ", strip=True
                )
            pub_tag = item.find("pubDate")
            pub = None
            if pub_tag:
                try:
                    from email.utils import parsedate_to_datetime
                    pub = parsedate_to_datetime(pub_tag.get_text(strip=True)).isoformat()
                except Exception:
                    pub = pub_tag.get_text(strip=True)
            articles.append(
                {"title": title, "url": link, "summary": summary, "published_at": pub}
            )
        return articles

    # ------------------------------------------------------------------
    # Main interface
    # ------------------------------------------------------------------

    def fetch_articles(self) -> list[Article]:
        """
        Fetch and return Article objects. Must be implemented by subclasses.
        """
        raise NotImplementedError

    def _sleep(self):
        """Polite delay between requests."""
        time.sleep(self.request_delay + random.uniform(0, 0.5))
