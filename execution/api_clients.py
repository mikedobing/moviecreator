import abc
import time
from typing import Dict, Any, Optional
from pydantic import BaseModel

class JobStatus(BaseModel):
    status: str                 # "queued" | "processing" | "completed" | "failed"
    progress: int               # 0-100
    eta_seconds: int | None
    error: str | None

class RateLimits(BaseModel):
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int

class BaseVideoAPIClient(abc.ABC):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    @abc.abstractmethod
    async def submit_job(self, prompt: Dict[str, Any]) -> str:
        """Submit generation job, return provider job ID"""
        pass

    @abc.abstractmethod
    async def poll_status(self, job_id: str) -> JobStatus:
        """Check job status"""
        pass

    @abc.abstractmethod
    async def get_result_url(self, job_id: str) -> str:
        """Get download URL for completed video"""
        pass

    @abc.abstractmethod
    def get_rate_limits(self) -> RateLimits:
        """Return API rate limit configuration"""
        pass

class SeedanceClient(BaseVideoAPIClient):
    """
    Seedance 2.0 API client
    """
    async def submit_job(self, prompt: Dict[str, Any]) -> str:
        # Placeholder for actual API call
        # In a real implementation, this would use httpx to POST to the API
        # For now, we'll return a dummy job ID provided by the caller or generate one
        return f"seedance_job_{int(time.time())}"

    async def poll_status(self, job_id: str) -> JobStatus:
        # Placeholder status
        return JobStatus(status=config.TEST_STATUS or "completed", progress=100, eta_seconds=0, error=None)

    async def get_result_url(self, job_id: str) -> str:
        # Placeholder URL
        return f"https://example.com/videos/{job_id}.mp4"

    def get_rate_limits(self) -> RateLimits:
        return RateLimits(
            requests_per_minute=30,
            requests_per_hour=1000,
            requests_per_day=10000
        )
