import logging
from app.common.exceptions.AppExceptions import ServiceUnavailableException, TooManyRequestsException
from app.core.AppConfig import AppConfig
from app.core.RedisManager import RedisManager

logger = logging.getLogger(__name__)


class RateLimiter:

    @staticmethod
    async def enforce(key: str, limit: int, window_seconds: int) -> None:
        """Increments a Redis counter and raises when the request limit is exceeded.

        Args:
            key (str): Unique rate limit bucket key.
            limit (int): Maximum requests allowed inside the window.
            window_seconds (int): Sliding window duration in seconds.

        Raises:
            TooManyRequestsException: If the request limit is exceeded.
            ServiceUnavailableException: If Redis is unavailable and fail-open is disabled.
        """
        if not AppConfig.RATE_LIMIT_ENABLED:
            return
        client = RedisManager.getClient()
        if client is None:
            if AppConfig.RATE_LIMIT_FAIL_OPEN:
                return
            raise ServiceUnavailableException(detail="Rate limiting service is unavailable.")

        try:
            current = await client.incr(key)
            if current == 1:
                await client.expire(key, window_seconds)
            if current > limit:
                retry_after = await client.ttl(key)
                raise TooManyRequestsException(
                    detail="Too many requests. Please try again later.",
                    retry_after=max(int(retry_after), 1),
                )
        except TooManyRequestsException:
            raise
        except Exception:
            logger.exception("Rate limiter failed for key %s.", key)
            if not AppConfig.RATE_LIMIT_FAIL_OPEN:
                raise ServiceUnavailableException(detail="Rate limiting service is unavailable.")
