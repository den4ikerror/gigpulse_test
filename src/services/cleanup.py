import asyncio
import logging
from src.database.session import async_session_maker
from src.database.repository import Repository

logger = logging.getLogger("gigpulse.cleanup")

async def cleanup_worker(interval_seconds: int = 3600):
    """Background task to remove orders older than 48 hours."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with async_session_maker() as session:
                deleted_count = await Repository.delete_old_orders(session, hours=48)
                if deleted_count > 0:
                    logger.info(f"Cleanup worker deleted {deleted_count} orders older than 48 hours.")
                deleted_posts = await Repository.delete_old_ingested_posts(session, days=7)
                if deleted_posts > 0:
                    logger.info("Cleanup worker deleted %d expired source posts older than 7 days", deleted_posts)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Cleanup worker failed")
