"""
Video generation job queue management.

Manages the queue of video generation jobs that Phase 4 will execute.
Jobs are stored in SQLite for persistence and crash resilience.
"""

import uuid
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from extraction.models import VideoPrompt, GenerationJob, QueueStats
from utils.logger import setup_logger

logger = setup_logger(__name__)


class JobQueue:
    """SQLite-backed FIFO job queue for video generation."""

    def __init__(self, db):
        """
        Args:
            db: Database instance (storage.database.Database)
        """
        self.db = db

    def add_job(self, prompt: VideoPrompt, api_provider: str = "seedance") -> GenerationJob:
        """Add a new job to the queue from a VideoPrompt."""
        job = GenerationJob(
            job_id=str(uuid.uuid4()),
            prompt_id=prompt.prompt_id,
            novel_id=prompt.novel_id,
            scene_id=prompt.scene_id,
            clip_index=prompt.clip_index,
            status="queued",
            api_provider=api_provider,
        )
        
        # Insert into database
        with self.db._get_connection() as conn:
            conn.execute(
                """INSERT INTO generation_jobs
                   (id, prompt_id, novel_id, scene_id, clip_index, status, api_provider, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job.job_id, job.prompt_id, job.novel_id, job.scene_id,
                 job.clip_index, job.status, job.api_provider, job.created_at)
            )
            conn.commit()
        
        return job

    def add_jobs_from_prompts(
        self, prompts: List[VideoPrompt], api_provider: str = "seedance"
    ) -> List[GenerationJob]:
        """Bulk-add jobs from a list of prompts."""
        jobs = []
        with self.db._get_connection() as conn:
            for prompt in prompts:
                job = GenerationJob(
                    job_id=str(uuid.uuid4()),
                    prompt_id=prompt.prompt_id,
                    novel_id=prompt.novel_id,
                    scene_id=prompt.scene_id,
                    clip_index=prompt.clip_index,
                    status="queued",
                    api_provider=api_provider,
                )
                conn.execute(
                    """INSERT INTO generation_jobs
                       (id, prompt_id, novel_id, scene_id, clip_index, status, api_provider, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (job.job_id, job.prompt_id, job.novel_id, job.scene_id,
                     job.clip_index, job.status, job.api_provider, job.created_at)
                )
                jobs.append(job)
            conn.commit()
        logger.info(f"Added {len(jobs)} jobs to queue for provider '{api_provider}'")
        return jobs

    def get_next_job(self, api_provider: Optional[str] = None) -> Optional[GenerationJob]:
        """Get the next queued job (FIFO order within scene/clip)."""
        with self.db._get_connection() as conn:
            if api_provider:
                row = conn.execute(
                    """SELECT * FROM generation_jobs
                       WHERE status = 'queued' AND api_provider = ?
                       ORDER BY created_at ASC LIMIT 1""",
                    (api_provider,)
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT * FROM generation_jobs
                       WHERE status = 'queued'
                       ORDER BY created_at ASC LIMIT 1"""
                ).fetchone()
        
        if row:
            return self._row_to_job(row)
        return None

    def mark_running(self, job_id: str) -> None:
        """Mark a job as currently running."""
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE generation_jobs SET status = 'running', started_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), job_id)
            )
            conn.commit()

    def mark_complete(
        self, job_id: str, output_path: str, cost: float, duration: int
    ) -> None:
        """Mark a job as successfully completed."""
        with self.db._get_connection() as conn:
            conn.execute(
                """UPDATE generation_jobs
                   SET status = 'complete', output_video_path = ?,
                       actual_cost_usd = ?, generation_time_seconds = ?,
                       completed_at = ?
                   WHERE id = ?""",
                (output_path, cost, duration, datetime.utcnow().isoformat(), job_id)
            )
            conn.commit()

    def mark_failed(self, job_id: str, error: str) -> None:
        """Mark a job as failed."""
        with self.db._get_connection() as conn:
            conn.execute(
                """UPDATE generation_jobs
                   SET status = 'failed', error_message = ?, completed_at = ?
                   WHERE id = ?""",
                (error, datetime.utcnow().isoformat(), job_id)
            )
            conn.commit()

    def get_queue_stats(self, novel_id: str) -> QueueStats:
        """Get queue statistics for a novel."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM generation_jobs WHERE novel_id = ? GROUP BY status",
                (novel_id,)
            ).fetchall()
        
        counts = {row[0]: row[1] for row in rows}
        total = sum(counts.values())

        # Estimate cost and duration from linked prompts
        with self.db._get_connection() as conn:
            cost_row = conn.execute(
                """SELECT SUM(vp.estimated_cost_usd), SUM(vp.duration_seconds)
                   FROM generation_jobs gj
                   JOIN video_prompts vp ON gj.prompt_id = vp.id
                   WHERE gj.novel_id = ?""",
                (novel_id,)
            ).fetchone()
        
        est_cost = cost_row[0] if cost_row and cost_row[0] else 0.0
        est_duration_sec = cost_row[1] if cost_row and cost_row[1] else 0
        
        return QueueStats(
            total_jobs=total,
            queued=counts.get("queued", 0),
            running=counts.get("running", 0),
            complete=counts.get("complete", 0),
            failed=counts.get("failed", 0),
            estimated_total_cost_usd=round(est_cost, 2),
            estimated_total_duration_minutes=round(est_duration_sec / 60.0, 1),
        )

    def export_queue(self, novel_id: str, output_path: str) -> None:
        """Export the job queue as JSON for Phase 4."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT gj.*, vp.prompt_text, vp.negative_prompt,
                          vp.duration_seconds as prompt_duration,
                          vp.aspect_ratio, vp.motion_intensity,
                          vp.camera_movement as prompt_camera,
                          vp.audio_prompt, vp.generation_params,
                          vp.character_consistency_tags
                   FROM generation_jobs gj
                   JOIN video_prompts vp ON gj.prompt_id = vp.id
                   WHERE gj.novel_id = ?
                   ORDER BY gj.scene_id, gj.clip_index""",
                (novel_id,)
            ).fetchall()
        
        jobs = []
        for row in rows:
            jobs.append({
                "job_id": row[0],
                "prompt_id": row[1],
                "novel_id": row[2],
                "scene_id": row[3],
                "clip_index": row[4],
                "status": row[5],
                "api_provider": row[6],
                "prompt_text": row[15] if len(row) > 15 else "",
                "negative_prompt": row[16] if len(row) > 16 else "",
                "duration_seconds": row[17] if len(row) > 17 else 8,
                "aspect_ratio": row[18] if len(row) > 18 else "16:9",
                "motion_intensity": row[19] if len(row) > 19 else "medium",
                "camera_movement": row[20] if len(row) > 20 else "static",
                "audio_prompt": row[21] if len(row) > 21 else "",
                "generation_params": self._safe_json_load(row[22]) if len(row) > 22 else {},
                "character_consistency_tags": self._safe_json_load(row[23]) if len(row) > 23 else [],
            })
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(jobs, f, indent=2)
        logger.info(f"Exported {len(jobs)} jobs to {output_path}")

    def _safe_json_load(self, data: Any) -> Any:
        """Safely load JSON data, returning default if failed."""
        if not data:
            return {}
        if isinstance(data, (dict, list)):
            return data
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to decode JSON data: {data}")
            return {}

    def _row_to_job(self, row) -> GenerationJob:
        """Convert a database row to GenerationJob."""
        return GenerationJob(
            job_id=row[0],
            prompt_id=row[1],
            novel_id=row[2],
            scene_id=row[3],
            clip_index=row[4],
            status=row[5],
            api_provider=row[6],
            api_job_id=row[7],
            output_video_path=row[8],
            generation_time_seconds=row[9],
            actual_cost_usd=row[10],
            error_message=row[11],
            created_at=row[12],
        )
