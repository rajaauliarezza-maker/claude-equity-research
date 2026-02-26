"""
Scraper for Bisnis.com (Bisnis Indonesia)
Uses Bisnis RSS feeds for pasar modal / emiten sections.
"""
import logging
from .base import BaseScraper, Article

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://www.bisnis.com/finansial/rss",
    "https://www.bisnis.com/market/rss",
    "https://www.bisnis.com/market/bursa-valas/saham/rss",
    "https://www.bisnis.com/market/ipo-right-issue/rss",
]

HTML_PAGES = [
    "https://www.bisnis.com/market",
    "https://www.bisnis.com/market/ipo-right-issue",
    "https://www.bisnis.com/finansial",
]


class BisnisScraper(BaseScraper):
    name = "Bisnis Indonesia"
    source_id = "bisnis"

    def fetch_articles(self) -> list[Article]:
        seen_urls: set[str] = set()
        raw: list[dict] = []

        # --- RSS ---
        for feed_url in RSS_FEEDS:
            logger.info("[%s] Fetching RSS: %s", self.source_id, feed_url)
            items = self._parse_rss(feed_url)
            for item in items:
                url = item.get("url", "").strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    raw.append(item)
            self._sleep()

        # --- HTML fallback ---
        if not raw:
            for page_url in HTML_PAGES:
                logger.info("[%s] Fetching HTML: %s", self.source_id, page_url)
                soup = self._soup(page_url)
                if soup is None:
                    continue
                # Bisnis.com article selectors
                for card in soup.select(
                    "article h2 a, .artikel a, .card-title a, h2.title a, .news-title a"
                )[: self.max_articles]:
                    url = card.get("href", "").strip()
                    title = card.get_text(strip=True)
                    if not url.startswith("http"):
                        url = "https://www.bisnis.com" + url
                    if url and title and url not in seen_urls:
                        seen_urls.add(url)
                        raw.append({"title": title, "url": url, "summary": None, "published_at": None})
                self._sleep()

        return [
            Article(
                source=self.name,
                title=item["title"],
                url=item["url"],
                summary=item.get("summary"),
                published_at=item.get("published_at"),
            )
            for item in raw
            if item.get("title") and item.get("url")
        ][: self.max_articles]
