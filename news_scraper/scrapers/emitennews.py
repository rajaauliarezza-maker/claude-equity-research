"""
Scraper for Emitennews.com
Emitennews focuses entirely on IDX-listed companies (emiten).
No official RSS; uses HTML scraping.
"""
import logging
from .base import BaseScraper, Article

logger = logging.getLogger(__name__)

BASE_URL = "https://emitennews.com"

# Pages to scrape (emitennews categorises by corporate action type)
PAGES = [
    f"{BASE_URL}/",
    f"{BASE_URL}/category/corporate-action/",
    f"{BASE_URL}/category/right-issue/",
    f"{BASE_URL}/category/buyback/",
    f"{BASE_URL}/category/akuisisi/",
    f"{BASE_URL}/category/dividen/",
]


class EmitenNewsScraper(BaseScraper):
    name = "Emitennews"
    source_id = "emitennews"

    def fetch_articles(self) -> list[Article]:
        seen_urls: set[str] = set()
        raw: list[dict] = []

        for page_url in PAGES:
            logger.info("[%s] Fetching HTML: %s", self.source_id, page_url)
            soup = self._soup(page_url)
            if soup is None:
                self._sleep()
                continue

            # Emitennews uses WordPress; standard selectors
            selectors = [
                "h2.entry-title a",
                "h3.entry-title a",
                ".post-title a",
                "article h2 a",
                "article h3 a",
                ".td-module-title a",
                "h3.td-module-title a",
                ".entry-title a",
            ]
            for sel in selectors:
                for a in soup.select(sel):
                    url = a.get("href", "").strip()
                    title = a.get_text(strip=True)
                    if url and title and url not in seen_urls:
                        seen_urls.add(url)
                        # Try to grab excerpt if present
                        parent = a.find_parent("article") or a.find_parent("div")
                        summary = None
                        if parent:
                            excerpt = parent.select_one(
                                ".entry-summary, .td-excerpt, .excerpt, p"
                            )
                            if excerpt:
                                summary = excerpt.get_text(separator=" ", strip=True)
                        raw.append(
                            {"title": title, "url": url, "summary": summary, "published_at": None}
                        )
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
