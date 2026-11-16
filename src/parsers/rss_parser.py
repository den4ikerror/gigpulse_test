import asyncio
import feedparser
import aiohttp
import logging
from src.parsers.base import BaseParser

logger = logging.getLogger("gigpulse.rss_parser")

class RSSParser(BaseParser):
    def __init__(self):
        super().__init__(name="RSS_Parser", interval_seconds=60)
        self.session: aiohttp.ClientSession | None = None
        self.feeds = [
            {"name": "Freelancehunt", "url": "https://freelancehunt.com/projects.rss"},
            {"name": "DOU Jobs", "url": "https://jobs.dou.ua/vacancies/feeds/"}
        ]

    async def start(self) -> None:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "GigPulse/1.0 RSS reader"},
            )

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    async def fetch_orders(self) -> list[dict]:
        await self.start()
        if self.session is None:
            raise RuntimeError("RSS client session failed to initialize")

        async def fetch_feed(feed_info: dict) -> list[dict]:
            try:
                async with self.session.get(feed_info["url"]) as response:
                    if response.status != 200:
                        logger.warning("Failed to fetch %s: status %s", feed_info["name"], response.status)
                        return []
                    parsed = feedparser.parse(await response.text())
                    orders = []
                    for entry in parsed.entries[:15]:
                        title = entry.get("title", "")
                        summary = entry.get("summary", entry.get("description", ""))
                        link = entry.get("link", "")
                        if not title or not link:
                            continue
                        orders.append({
                            "title": title,
                            "summary": summary,
                            "contact_url": link,
                            "source_name": feed_info["name"],
                            "budget": None,
                            "raw_text": f"{title}\n{summary}"
                        })
                    return orders
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error fetching RSS feed %s", feed_info["name"])
                return []

        results = await asyncio.gather(*(fetch_feed(feed) for feed in self.feeds))
        return [order for feed_orders in results for order in feed_orders]
