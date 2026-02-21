"""
Scraper for Kontan.co.id
Uses Kontan's RSS feeds for market/investasi/emiten sections.
Falls back to HTML scraping of the market news page.
"""
import logging
from .base import BaseScraper, Article

logger = logging.getLogger(__name__)

# Kontan RSS feeds most relevant to equity coverage
RSS_FEEDS = [
    ("https://rss.kontan.co.id/category/emiten",     "emiten"),
    ("https://rss.kontan.co.id/category/investasi",   "investasi"),
    ("https://rss.kontan.co.id/category/market",      "market"),
    ("https://rss.kontan.co.id/category/saham",       "saham"),
]

# HTML fallback pages
HTML_PAGES = [
    "https://www.kontan.co.id/news/emiten",
    "https://www.kontan.co.id/news/saham",
]


class KontanScraper(BaseScraper):
    name = "Kontan"
    source_id = "kontan"

    def fetch_articles(self) -> list[Article]:
        seen_urls: set[str] = set()
        raw: list[dict] = []

        # --- RSS first (preferred) ---
        for feed_url, label in RSS_FEEDS:
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
                # Kontan article links in news list
                for a in soup.select("h2 > a, h3 > a, .list-news a")[:self.max_articles]:
                    url = a.get("href", "").strip()
                    title = a.get_text(strip=True)
                    if url and title and url not in seen_urls:
                        if not url.startswith("http"):
                            url = "https://www.kontan.co.id" + url
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
