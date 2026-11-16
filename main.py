import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from aiogram import Bot, Dispatcher
from src.config import settings
from src.database.session import async_session_maker, engine
from src.database.models import Base
from src.database.repository import Repository
from src.ai.prefilter import PreFilter
from src.ai.llm_router import LLMRouter
from src.ai.batcher import Batcher
from src.parsers.rss_parser import RSSParser
from src.parsers.tg_parser import TelegramParser
from src.bot.handlers.start import router as start_router
from src.bot.notifier import Notifier
from src.services.cleanup import cleanup_worker

from src.api.orders import router as orders_router
from src.api.user import router as user_router
from src.api.payments import router as payments_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("gigpulse")

app = FastAPI(title="GigPulse API", version="1.0.0")

# Include API Routers
app.include_router(orders_router)
app.include_router(user_router)
app.include_router(payments_router)

# Mount static webapp
app.mount("/", StaticFiles(directory="webapp", html=True), name="webapp")

# Telegram Bot Setup
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
if start_router.parent_router is None and not (__name__ == "__main__" and settings.DEBUG):
    dp.include_router(start_router)

prefilter = PreFilter()
llm_router = LLMRouter()
notifier = Notifier(bot)

async def persist_batch(batch: list[dict]) -> None:
    """Persist raw posts before AI processing so provider failures do not lose them."""
    posts = []
    for post in batch:
        if prefilter.is_spam(post["raw_text"]):
            continue
        posts.append({
            **post,
            "hash_id": prefilter.get_hash(post["raw_text"], post["contact_url"]),
        })
    if not posts:
        return

    async with async_session_maker() as session:
        added = await Repository.enqueue_posts(session, posts)
        if added:
            logger.info("Persisted %d new posts for classification", added)

batcher = Batcher(callback=persist_batch, batch_size=6, timeout_seconds=10.0)
background_tasks: set[asyncio.Task] = set()
tg_parser: TelegramParser | None = None


def start_background_task(coro, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    background_tasks.add(task)

    def task_done(done_task: asyncio.Task) -> None:
        background_tasks.discard(done_task)
        if done_task.cancelled():
            return
        error = done_task.exception()
        if error:
            logger.error(
                "Background task %s failed",
                done_task.get_name(),
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(task_done)
    return task


async def rss_poller(stop_event: asyncio.Event):
    rss = RSSParser()
    try:
        await rss.start()
        while not stop_event.is_set():
            try:
                orders = await rss.fetch_orders()
                for order in orders:
                    await batcher.add(order)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("RSS poll failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60)
            except TimeoutError:
                pass
    finally:
        await rss.close()

async def telegram_polling_worker():
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot, handle_signals=False, close_bot_session=False)
            logger.warning("Telegram polling stopped unexpectedly; restarting in 5 seconds")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram polling failed; retrying in 5 seconds")
            await asyncio.sleep(5)

async def ingestion_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        posts = []
        try:
            async with async_session_maker() as session:
                pending_notifications = await Repository.get_pending_notifications(session)
                if pending_notifications:
                    notified_ids = []
                    failed_notifications = []
                    for post, order in pending_notifications:
                        if await notifier.notify_new_order(session, order):
                            notified_ids.append(post.id)
                        else:
                            failed_notifications.append(post.id)
                    await Repository.mark_ingested_posts_notified(
                        session,
                        notified_ids,
                    )
                    if failed_notifications:
                        await Repository.defer_ingested_posts_by_ids(
                            session,
                            failed_notifications,
                            "One or more Telegram notifications failed",
                        )
                    continue
                posts = await Repository.get_pending_posts(session, limit=6)
            if not posts:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=1)
                except TimeoutError:
                    pass
                continue

            classifications = await llm_router.classify_batch([
                {
                    "title": post.title,
                    "summary": post.summary,
                    "raw_text": post.raw_text,
                    "source_name": post.source_name,
                }
                for post in posts
            ])
            by_index = {item["index"]: item for item in classifications}
            irrelevant_count = sum(
                item["category"] == "irrelevant"
                for item in classifications
            )
            async with async_session_maker() as session:
                orders = await Repository.complete_ingested_posts(
                    session,
                    posts,
                    {post.id: by_index[index] for index, post in enumerate(posts)},
                )
                if irrelevant_count:
                    logger.info("Filtered %d unrelated posts", irrelevant_count)
                for order in orders:
                    logger.info("New order classified: [%s] %s", order.category, order.title)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Ingestion worker failed; pending posts will be retried")
            if posts:
                try:
                    async with async_session_maker() as session:
                        await Repository.defer_ingested_posts_by_ids(
                            session,
                            [post.id for post in posts],
                            str(error),
                        )
                except Exception:
                    logger.exception("Could not update retry schedule for ingested posts")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2)
            except TimeoutError:
                pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    global tg_parser
    stop_event = asyncio.Event()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    batcher.closed = False
    tg_parser = TelegramParser(callback=batcher.add)
    tasks = [
        start_background_task(rss_poller(stop_event), "rss-poller"),
        start_background_task(cleanup_worker(3600), "cleanup-worker"),
        start_background_task(ingestion_worker(stop_event), "ingestion-worker"),
        start_background_task(telegram_polling_worker(), "telegram-polling"),
        start_background_task(tg_parser.start(), "telegram-channel-parser"),
    ]
    try:
        yield
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await batcher.close()
        except Exception:
            logger.exception("Could not flush the ingestion batch during shutdown")
        if tg_parser:
            await tg_parser.close()
            tg_parser = None
        await bot.session.close()
        await engine.dispose()


app.router.lifespan_context = lifespan

if __name__ == "__main__":
    if settings.DEBUG:
        uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
