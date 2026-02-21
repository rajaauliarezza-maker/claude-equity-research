"""
Scraper for The Jakarta Post
Uses Jakarta Post RSS + HTML scraping for business/finance sections.
"""
import logging
from .base import BaseScraper, Article

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://www.thejakartapost.com/rss/business.xml",
    "https://www.thejakartapost.com/rss/economy.xml",
]

HTML_PAGES = [
    "https://www.thejakartapost.com/business",
    "https://www.thejakartapost.com/economy",
]


class JakartaPostScraper(BaseScraper):
    name = "Jakarta Post"
    source_id = "jakartapost"

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
                for a in soup.select(
                    "h2 a, h3 a, .article-title a, .story-title a, "
                    ".title a, article header a"
                )[: self.max_articles]:
                    url = a.get("href", "").strip()
                    title = a.get_text(strip=True)
                    if not url.startswith("http"):
                        url = "https://www.thejakartapost.com" + url
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
