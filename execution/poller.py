import asyncio
import time
from typing import List, Tuple, Any
from pydantic import BaseModel
from .api_clients import BaseVideoAPIClient, JobStatus

class PollResult(BaseModel):
    job_id: str
    status: str
    video_url: str | None
    error: str | None

class AsyncJobPoller:
    def __init__(self, client: BaseVideoAPIClient, db: Any):
        self.client = client
        self.db = db

    async def poll_until_complete(
        self,
        job_id: str,
        provider_job_id: str,
        max_wait_seconds: int = 300,
        poll_interval_seconds: int = 5
    ) -> PollResult:
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait_seconds:
            try:
                status = await self.client.poll_status(provider_job_id)
                
                if status.status == "completed":
                    video_url = await self.client.get_result_url(provider_job_id)
                    return PollResult(
                        job_id=job_id,
                        status="completed",
                        video_url=video_url,
                        error=None
                    )
                
                if status.status == "failed":
                    return PollResult(
                        job_id=job_id,
                        status="failed",
                        video_url=None,
                        error=status.error or "Unknown failure"
                    )
                
                # Still processing
                await asyncio.sleep(poll_interval_seconds)
                
                # Simple backoff logic could go here
                
            except Exception as e:
                # Log error and retry polling (maybe with backoff)
                # For now just continue
                await asyncio.sleep(poll_interval_seconds)
                
        return PollResult(
            job_id=job_id,
            status="timeout",
            video_url=None,
            error="Polling timed out"
        )
