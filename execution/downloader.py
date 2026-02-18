import os
import httpx
import aiofiles
from pathlib import Path
from pydantic import BaseModel

class DownloadResult(BaseModel):
    success: bool
    file_path: str | None
    file_size_bytes: int | None
    error: str | None

class VideoDownloader:
    def __init__(self, output_base_path: str):
        self.output_base_path = Path(output_base_path)

    async def download(
        self,
        video_url: str,
        job_id: str,
        novel_id: str,
        scene_id: str,
        clip_index: int
    ) -> DownloadResult:
        try:
            # Create directory structure
            scene_dir = self.output_base_path / "clips" / novel_id / scene_id
            scene_dir.mkdir(parents=True, exist_ok=True)
            
            # Filename: clip_001.mp4
            filename = f"clip_{clip_index:03d}.mp4"
            file_path = scene_dir / filename
            
            async with httpx.AsyncClient() as client:
                response = await client.get(video_url)
                response.raise_for_status()
                
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(response.content)
            
            return DownloadResult(
                success=True,
                file_path=str(file_path),
                file_size_bytes=file_path.stat().st_size,
                error=None
            )
            
        except Exception as e:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size_bytes=None,
                error=str(e)
            )

    async def download_with_verification(
        self,
        video_url: str,
        job_id: str,
        novel_id: str,
        scene_id: str,
        clip_index: int,
        expected_duration_seconds: int
    ) -> DownloadResult:
        # For now, just call download. Verification can be added later.
        return await self.download(video_url, job_id, novel_id, scene_id, clip_index)
