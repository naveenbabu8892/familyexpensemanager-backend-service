import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

from app.core.config import settings


class InMemoryRateLimiter:
    """
    Sliding window in-memory rate limiter for brute-force and DDoS mitigation.
    Tracks timestamps per client IP.
    """

    def __init__(self):
        # Maps client_ip:endpoint -> list of request timestamps
        self.history: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        request: Request,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_prefix: str = "general",
    ) -> None:
        """
        Verify request rate for the calling client IP.
        Raises HTTP 429 if the request threshold is exceeded.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return

        # Bypass rate limiter during unit test runner unless explicitly testing it
        if settings.ENVIRONMENT == "testing" and not request.headers.get("X-Test-Rate-Limit"):
            return

        client_ip = request.client.host if request.client else "unknown"
        bucket_key = f"{key_prefix}:{client_ip}"
        now = time.time()
        cutoff = now - window_seconds

        # Clean entries outside the window
        timestamps = [ts for ts in self.history[bucket_key] if ts > cutoff]
        self.history[bucket_key] = timestamps

        if len(timestamps) >= max_requests:
            retry_after = int(window_seconds - (now - timestamps[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        # Record this request
        self.history[bucket_key].append(now)


# Global rate limiter instance
limiter = InMemoryRateLimiter()
