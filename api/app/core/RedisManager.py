import logging
from redis.asyncio import Redis
from app.core.AppConfig import AppConfig

logger = logging.getLogger(__name__)


class RedisManager:

    client: Redis | None = None

    @classmethod
    async def connect(cls) -> None:
        """Initializes the asynchronous Redis client and verifies connectivity."""
        if cls.client is not None:
            return
        try:
            client = Redis.from_url(AppConfig.REDIS_URL, decode_responses=True)
            await client.ping()
            cls.client = client
        except Exception:
            logger.exception("Redis is unavailable; rate limiting will fail open.")

    @classmethod
    async def close(cls) -> None:
        """Closes the active Redis connection pool."""
        if cls.client is not None:
            await cls.client.aclose()
            cls.client = None

    @classmethod
    def getClient(cls) -> Redis | None:
        """Returns the active Redis client when available.

        Returns:
            Redis | None: Connected Redis client or None when unavailable.
        """
        return cls.client
