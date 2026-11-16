import asyncio
import logging
from src.config import settings
from src.parsers.base import BaseParser

logger = logging.getLogger("gigpulse.tg_parser")

try:
    from telethon import TelegramClient
    from telethon.events import NewMessage
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

class TelegramParser(BaseParser):
    def __init__(self, callback=None):
        super().__init__(name="Telegram_Parser", interval_seconds=30)
        self.callback = callback
        self.client = None
        self.channels = [channel.strip().lstrip("@") for channel in settings.TG_CHANNELS.split(",") if channel.strip()]
        self.stopping = False

    async def start(self):
        if not TELETHON_AVAILABLE or not settings.TG_API_ID or not settings.TG_API_HASH:
            logger.info("Telegram UserBot (Telethon) credentials not configured or library missing. Skipping Telegram monitoring.")
            return

        self.stopping = False
        retry_delay = 5
        while not self.stopping:
            try:
                self.client = TelegramClient(
                    settings.TG_SESSION_NAME,
                    settings.TG_API_ID,
                    settings.TG_API_HASH
                )
                await self.client.start()
                logger.info("Telegram UserBot started successfully.")
                retry_delay = 5

                @self.client.on(NewMessage(chats=self.channels))
                async def handle_new_message(event):
                    msg = event.message
                    if not msg.text:
                        return
                    username = getattr(event.chat, "username", None)
                    contact_url = f"https://t.me/{username}/{msg.id}" if username else "https://t.me"
                    order_data = {
                        "title": msg.text[:100] + ("..." if len(msg.text) > 100 else ""),
                        "summary": msg.text,
                        "contact_url": contact_url,
                        "source_name": f"Telegram: @{username or 'channel'}",
                        "budget": None,
                        "raw_text": msg.text
                    }
                    if self.callback:
                        await self.callback(order_data)

                await self.client.run_until_disconnected()
                if not self.stopping:
                    logger.warning("Telegram UserBot disconnected; reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram UserBot failed; retrying in %d seconds", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            finally:
                if self.client:
                    await self.client.disconnect()
                    self.client = None

    async def close(self):
        self.stopping = True
        if self.client:
            await self.client.disconnect()

    async def fetch_orders(self) -> list[dict]:
        # Telethon operates via event listener in background
        return []
