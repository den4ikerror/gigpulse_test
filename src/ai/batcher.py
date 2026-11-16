import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger("gigpulse.batcher")
_STOP = object()


class Batcher:
    def __init__(
        self,
        callback: Callable[[list[dict]], Awaitable[None]],
        batch_size: int = 6,
        timeout_seconds: float = 10.0,
        max_queue_size: int = 1000,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.callback = callback
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.queue: asyncio.Queue[dict | object] = asyncio.Queue(maxsize=max_queue_size)
        self.worker_task: asyncio.Task | None = None
        self.closed = False

    async def add(self, item: dict) -> None:
        if self.closed:
            raise RuntimeError("Cannot add items to a closed batcher")
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._run())
        await self.queue.put(item)

    async def _deliver(self, batch: list[dict]) -> None:
        delay = 1.0
        while True:
            try:
                await self.callback(batch)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Batch persistence failed; retrying %d items in %.1f seconds", len(batch), delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

    async def _run(self) -> None:
        batch: list[dict] = []
        while True:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=self.timeout_seconds)
            except TimeoutError:
                if batch:
                    await self._deliver(batch)
                    for _ in batch:
                        self.queue.task_done()
                    batch = []
                continue

            if item is _STOP:
                if batch:
                    await self._deliver(batch)
                    for _ in batch:
                        self.queue.task_done()
                self.queue.task_done()
                return

            if not isinstance(item, dict):
                raise TypeError("Batch queue only accepts dictionaries")
            batch.append(item)
            if len(batch) >= self.batch_size:
                await self._deliver(batch)
                for _ in batch:
                    self.queue.task_done()
                batch = []

    async def close(self, timeout_seconds: float = 15.0) -> None:
        if self.closed:
            if self.worker_task:
                await self.worker_task
            return
        self.closed = True
        if self.worker_task is None:
            return
        await self.queue.put(_STOP)
        try:
            await asyncio.wait_for(asyncio.shield(self.worker_task), timeout=timeout_seconds)
        except TimeoutError:
            self.worker_task.cancel()
            await asyncio.gather(self.worker_task, return_exceptions=True)
            raise RuntimeError(
                f"Batcher shutdown timed out with {self.queue.qsize()} queued items"
            )
