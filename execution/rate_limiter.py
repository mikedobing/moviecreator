import time
import asyncio
from typing import Dict, Any

class RateLimitStatus:
    def __init__(self, provider: str, can_proceed: bool, wait_seconds: float = 0):
        self.provider = provider
        self.can_proceed = can_proceed
        self.wait_seconds = wait_seconds

class RateLimiter:
    def __init__(self, db: Any):
        self.db = db
        # In-memory cache for simple rate limiting
        self.limits = {
            "seedance": {"rpm": 30, "last_request": 0},
            "kling": {"rpm": 10, "last_request": 0}
        }

    async def acquire(self, api_provider: str) -> None:
        """Block until rate limit allows request"""
        if api_provider not in self.limits:
            return

        limit_info = self.limits[api_provider]
        rpm = limit_info["rpm"]
        interval = 60.0 / rpm
        
        last_request = limit_info["last_request"]
        now = time.time()
        
        elapsed = now - last_request
        if elapsed < interval:
            wait_time = interval - elapsed
            await asyncio.sleep(wait_time)
            
        self.limits[api_provider]["last_request"] = time.time()

    def record_request(self, api_provider: str) -> None:
        if api_provider in self.limits:
            self.limits[api_provider]["last_request"] = time.time()
