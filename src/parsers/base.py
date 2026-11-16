import abc
import logging

logger = logging.getLogger("gigpulse.parser")

class BaseParser(abc.ABC):
    def __init__(self, name: str, interval_seconds: int = 60):
        self.name = name
        self.interval_seconds = interval_seconds

    @abc.abstractmethod
    async def fetch_orders(self) -> list[dict]:
        """Fetch raw orders from source and return a list of dicts."""
        pass
