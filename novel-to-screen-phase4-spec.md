# Novel-to-Screen Pipeline — Phase 4 Build Spec
## Video Generation Execution & Assembly

**Version:** 1.0  
**Stack:** Python 3.11+  
**Depends on:** Phase 3 output (Job Queue, Video Prompts)  
**Input:** Generation job queue + prompts from SQLite  
**Output:** Generated video clips + assembled scene videos  

---

## Overview

Phase 4 is the execution layer. It takes the job queue from Phase 3 and:

1. **Executes video generation API calls** against Seedance 2.0, Kling, or other providers
2. **Handles async job polling** - video generation takes 30s-2min per clip
3. **Downloads and stores generated clips** with proper naming and metadata
4. **Assembles clips into complete scenes** using FFmpeg
5. **Tracks costs and generation metrics** in real-time
6. **Provides robust retry logic** for failed generations
7. **Manages rate limits** to avoid API throttling

This phase is the most operationally complex because it deals with:
- Network failures and timeouts
- API rate limits and quotas
- Long-running async jobs
- Large file downloads and storage
- Video encoding and assembly

**Key principle:** The system must be resilient. If a job fails at clip 47 of 100, the user should be able to resume from clip 48 without regenerating everything.

---

## Project Structure

Extend `novel_pipeline/`:

```
novel_pipeline/
├── ... (Phase 1-3 files unchanged)
│
├── execution/
│   ├── __init__.py
│   ├── job_executor.py               # Main execution orchestrator
│   ├── api_clients.py                # Actual API client implementations
│   ├── poller.py                     # Async job polling logic
│   ├── downloader.py                 # Video file download and storage
│   ├── retry_handler.py              # Exponential backoff retry logic
│   └── rate_limiter.py               # API rate limit management
│
├── assembly/
│   ├── __init__.py
│   ├── clip_assembler.py             # FFmpeg-based clip assembly
│   ├── scene_compiler.py             # Compile clips into complete scenes
│   ├── audio_mixer.py                # Audio adjustment and mixing (optional)
│   └── metadata_writer.py            # Embed metadata in final videos
│
├── monitoring/
│   ├── __init__.py
│   ├── progress_tracker.py           # Real-time progress display
│   ├── cost_tracker.py               # Track actual costs vs estimates
│   └── error_reporter.py             # Structured error logging
│
├── storage/
│   ├── ... (Phase 1-3 files unchanged)
│   └── schema_phase4.sql             # Generation metrics tables
│
└── output/
    ├── clips/                        # Individual generated clips
    │   └── <novel_id>/
    │       └── <scene_id>/
    │           └── clip_000.mp4
    ├── scenes/                       # Assembled scene videos
    │   └── <novel_id>/
    │       └── scene_001.mp4
    └── final/                        # Full assembled novel video (optional)
        └── <novel_title>_complete.mp4
```

---

## Additional Dependencies

```
httpx>=0.27.0             # Modern async HTTP client
tenacity>=8.0.0           # Retry logic with exponential backoff
tqdm>=4.66.0              # Progress bars
ffmpeg-python>=0.2.0      # Video assembly
aiofiles>=23.0.0          # Async file operations
websockets>=12.0          # For SSE/WebSocket APIs (Seedance 2.0)
```

**System dependencies:**
- **FFmpeg** (required) - Install via apt/brew/choco
- Sufficient disk space (~500MB per 10min of generated video at 1080p)

---

## Additional SQLite Tables

```sql
-- schema_phase4.sql

CREATE TABLE IF NOT EXISTS generation_metrics (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,         -- "api_call" | "download" | "assembly" | "retry"
    timestamp TEXT NOT NULL,
    duration_seconds REAL,
    cost_usd REAL,
    details TEXT,                      -- JSON with additional context
    FOREIGN KEY (job_id) REFERENCES generation_jobs(id)
);

CREATE TABLE IF NOT EXISTS api_rate_limits (
    id TEXT PRIMARY KEY,
    api_provider TEXT NOT NULL UNIQUE,
    requests_per_minute INTEGER,
    requests_per_hour INTEGER,
    requests_per_day INTEGER,
    current_minute_count INTEGER DEFAULT 0,
    current_hour_count INTEGER DEFAULT 0,
    current_day_count INTEGER DEFAULT 0,
    window_reset_at TEXT,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS download_cache (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    provider_video_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    checksum TEXT,                     -- SHA256 for integrity verification
    downloaded_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES generation_jobs(id)
);

CREATE TABLE IF NOT EXISTS assembly_log (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    clip_count INTEGER,
    total_duration_seconds REAL,
    output_path TEXT NOT NULL,
    ffmpeg_command TEXT,
    assembly_time_seconds REAL,
    status TEXT,                       -- "success" | "failed"
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id)
);
```

---

## Module Specifications

---

### 1. `execution/api_clients.py`

**Purpose:** Actual API client implementations for each video generation provider.

**Base class:**

```python
class BaseVideoAPIClient(ABC):
    def __init__(self, api_key: str, base_url: str)
    
    @abstractmethod
    async def submit_job(self, prompt: VideoPrompt) -> str:
        """Submit generation job, return provider job ID"""
        pass
    
    @abstractmethod
    async def poll_status(self, job_id: str) -> JobStatus:
        """Check job status"""
        pass
    
    @abstractmethod
    async def get_result_url(self, job_id: str) -> str:
        """Get download URL for completed video"""
        pass
    
    @abstractmethod
    def get_rate_limits(self) -> RateLimits:
        """Return API rate limit configuration"""
        pass
```

**Seedance 2.0 client:**

```python
class SeedanceClient(BaseVideoAPIClient):
    """
    Seedance 2.0 API client (ByteDance Volcano Engine / third-party platforms)
    
    API architecture: Async job-based
    1. POST /v1/video/generation -> returns job_id
    2. GET /v1/video/status/{job_id} -> poll until complete
    3. GET /v1/video/download/{job_id} -> download URL
    
    Expected generation time: 30-120 seconds per clip
    """
    
    async def submit_job(self, prompt: VideoPrompt) -> str:
        """
        Submit video generation job
        
        Request body:
        {
            "prompt": str,
            "negative_prompt": str,
            "duration": int,           # 4-15 seconds
            "resolution": str,         # "480p" | "720p" | "1080p" | "2k"
            "aspect_ratio": str,       # "16:9" | "9:16" | "1:1"
            "motion_intensity": str,   # "low" | "medium" | "high"
            "audio_enabled": bool,
            "audio_prompt": str,       # If audio_enabled
            "reference_images": list,  # Optional: up to 9 images
            "reference_videos": list,  # Optional: up to 3 videos
        }
        """
        pass
    
    async def poll_status(self, job_id: str) -> JobStatus:
        """
        Poll job status
        
        Response:
        {
            "status": "queued" | "processing" | "completed" | "failed",
            "progress": int,           # 0-100
            "eta_seconds": int,
            "error": str | null
        }
        """
        pass
```

**Kling client:**

```python
class KlingClient(BaseVideoAPIClient):
    """
    Kling API client (Kuaishou)
    
    Similar async pattern to Seedance
    Supports up to 10s clips
    Pricing: ~$0.15-0.30 per clip
    """
    pass
```

**Error handling:**

Each client must handle:
- **HTTP 429 (Rate Limit)** - exponential backoff and retry
- **HTTP 503 (Service Unavailable)** - retry with backoff
- **HTTP 400 (Bad Request)** - log prompt, mark job as failed (don't retry)
- **Timeout errors** - retry up to 3 times
- **Network errors** - retry with exponential backoff

---

### 2. `execution/poller.py`

**Purpose:** Manage polling of async video generation jobs.

**Class: `AsyncJobPoller`**

```python
class AsyncJobPoller:
    def __init__(self, client: BaseVideoAPIClient, db: Database)
    
    async def poll_until_complete(
        self,
        job_id: str,
        provider_job_id: str,
        max_wait_seconds: int = 300,
        poll_interval_seconds: int = 5
    ) -> PollResult
    
    async def poll_multiple_jobs(
        self,
        jobs: list[tuple[str, str]],    # (job_id, provider_job_id) pairs
        max_concurrent: int = 10
    ) -> list[PollResult]
    
    def _calculate_next_poll_interval(self, attempts: int) -> int:
        """Exponential backoff: 5s, 10s, 20s, 40s, 60s (capped)"""
        pass
```

**Polling strategy:**

- Start with 5-second intervals
- If job still processing after 30 seconds, increase to 10-second intervals
- After 60 seconds, increase to 20-second intervals
- Cap at 60-second intervals for very long jobs
- If job hasn't completed after `max_wait_seconds`, mark as timeout and log for manual review

**Concurrent polling:**

Poll multiple jobs simultaneously (up to 10 concurrent) to maximize throughput. Use `asyncio.gather()` to manage concurrent polling tasks.

---

### 3. `execution/downloader.py`

**Purpose:** Download generated video files from provider URLs.

**Class: `VideoDownloader`**

```python
class VideoDownloader:
    def __init__(self, output_base_path: str)
    
    async def download(
        self,
        video_url: str,
        job_id: str,
        scene_id: str,
        clip_index: int
    ) -> str:
        """Download video, return local file path"""
        pass
    
    async def download_with_verification(
        self,
        video_url: str,
        job_id: str,
        scene_id: str,
        clip_index: int,
        expected_duration_seconds: int
    ) -> DownloadResult
    
    def _verify_video_integrity(self, file_path: str, expected_duration: int) -> bool:
        """Use FFprobe to check video is valid and expected duration"""
        pass
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 for deduplication"""
        pass
```

**Download strategy:**

1. Create directory structure: `output/clips/<novel_id>/<scene_id>/`
2. Download to temp file first: `clip_<index>.tmp.mp4`
3. Verify file integrity with FFprobe
4. Calculate checksum
5. Rename to final name: `clip_<index>.mp4`
6. Store metadata in `download_cache` table
7. Delete temp file on failure

**File naming convention:**

```
output/clips/<novel_id>/<scene_id>/clip_000.mp4
output/clips/<novel_id>/<scene_id>/clip_001.mp4
output/clips/<novel_id>/<scene_id>/clip_002.mp4
```

Zero-padded to 3 digits (supports up to 999 clips per scene).

---

### 4. `execution/retry_handler.py`

**Purpose:** Robust retry logic with exponential backoff.

**Class: `RetryHandler`**

```python
class RetryHandler:
    def __init__(self, max_retries: int = 3, base_delay: float = 2.0)
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry"""
        pass
    
    def should_retry(self, error: Exception) -> bool:
        """Determine if error is retryable"""
        pass
    
    def calculate_delay(self, attempt: int) -> float:
        """Exponential backoff: 2s, 4s, 8s, 16s"""
        pass
```

**Retryable errors:**
- Network timeouts
- HTTP 429 (rate limit)
- HTTP 503 (service unavailable)
- Temporary API errors (5xx range)

**Non-retryable errors:**
- HTTP 400 (bad request - prompt issue)
- HTTP 401 (auth failure)
- HTTP 404 (job not found)
- Video verification failures (corrupted download)

---

### 5. `execution/rate_limiter.py`

**Purpose:** Prevent API throttling by respecting rate limits.

**Class: `RateLimiter`**

```python
class RateLimiter:
    def __init__(self, db: Database)
    
    async def acquire(self, api_provider: str) -> None:
        """Block until rate limit allows request"""
        pass
    
    def record_request(self, api_provider: str) -> None:
        """Increment counters for rate limit tracking"""
        pass
    
    def reset_window_if_needed(self, api_provider: str) -> None:
        """Reset counters if time window has passed"""
        pass
    
    def get_current_limits(self, api_provider: str) -> RateLimitStatus:
        """Return current usage vs limits"""
        pass
```

**Rate limit configuration (Seedance 2.0 estimates):**

Based on typical API patterns:
- **Requests per minute:** 30
- **Requests per hour:** 1000
- **Requests per day:** 10000

These are conservative estimates. Actual limits should be configurable via environment variables.

**Rate limit strategy:**

- Track requests in sliding time windows
- If approaching limit (e.g. 90% of quota), inject delays
- Use token bucket algorithm for smooth request distribution
- If rate limit error occurs, immediately back off for 60 seconds

---

### 6. `execution/job_executor.py`

**Purpose:** Main orchestrator for executing the job queue.

**Class: `JobExecutor`**

```python
class JobExecutor:
    def __init__(
        self,
        db: Database,
        client: BaseVideoAPIClient,
        poller: AsyncJobPoller,
        downloader: VideoDownloader,
        rate_limiter: RateLimiter,
        retry_handler: RetryHandler
    )
    
    async def execute_queue(
        self,
        novel_id: str,
        max_concurrent_jobs: int = 5,
        resume: bool = True
    ) -> ExecutionReport
    
    async def execute_single_job(self, job: GenerationJob) -> JobResult
    
    def _update_job_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None
    ) -> None
    
    async def _record_metrics(
        self,
        job_id: str,
        metric_type: str,
        duration: float,
        cost: float,
        details: dict
    ) -> None
```

**Execution flow for a single job:**

```python
async def execute_single_job(self, job: GenerationJob) -> JobResult:
    """
    1. Load prompt from database
    2. Check rate limiter
    3. Submit job to API (with retry)
    4. Poll until complete (with timeout)
    5. Download video file (with verification)
    6. Update job status to 'complete'
    7. Record metrics (time, cost)
    8. Return result
    """
    
    # Step 1: Load prompt
    prompt = self.db.get_prompt(job.prompt_id)
    
    # Step 2: Rate limit check
    await self.rate_limiter.acquire(job.api_provider)
    
    # Step 3: Submit job
    start_time = time.time()
    provider_job_id = await self.retry_handler.execute_with_retry(
        self.client.submit_job,
        prompt
    )
    self.db.update_job(job.job_id, api_job_id=provider_job_id, status='running')
    
    # Step 4: Poll until complete
    poll_result = await self.poller.poll_until_complete(
        job.job_id,
        provider_job_id,
        max_wait_seconds=300
    )
    
    if poll_result.status == 'failed':
        self.db.update_job(job.job_id, status='failed', error=poll_result.error)
        return JobResult(success=False, error=poll_result.error)
    
    # Step 5: Download video
    video_url = await self.client.get_result_url(provider_job_id)
    download_result = await self.downloader.download_with_verification(
        video_url,
        job.job_id,
        job.scene_id,
        job.clip_index,
        prompt.duration_seconds
    )
    
    if not download_result.success:
        self.db.update_job(job.job_id, status='failed', error=download_result.error)
        return JobResult(success=False, error=download_result.error)
    
    # Step 6: Update job status
    generation_time = time.time() - start_time
    actual_cost = self._calculate_actual_cost(prompt, job.api_provider)
    
    self.db.update_job(
        job.job_id,
        status='complete',
        output_video_path=download_result.file_path,
        generation_time_seconds=int(generation_time),
        actual_cost_usd=actual_cost
    )
    
    # Step 7: Record metrics
    await self._record_metrics(
        job.job_id,
        'api_call',
        generation_time,
        actual_cost,
        {'provider_job_id': provider_job_id}
    )
    
    return JobResult(success=True, file_path=download_result.file_path)
```

**Concurrent execution:**

Execute up to `max_concurrent_jobs` (default 5) simultaneously using `asyncio.gather()` with `return_exceptions=True` to prevent one failure from killing the entire batch.

**Resume capability:**

If `resume=True`, skip jobs already marked as 'complete'. This allows the user to restart execution after a crash or manual stop without regenerating completed clips.

---

### 7. `assembly/clip_assembler.py`

**Purpose:** Assemble individual clips into complete scene videos.

**Class: `ClipAssembler`**

```python
class ClipAssembler:
    def __init__(self, ffmpeg_path: str = 'ffmpeg')
    
    def assemble_scene(
        self,
        scene_id: str,
        clip_paths: list[str],
        output_path: str,
        transition_type: str = 'cut'
    ) -> AssemblyResult
    
    def _create_concat_file(self, clip_paths: list[str], temp_dir: str) -> str:
        """Create FFmpeg concat demuxer file"""
        pass
    
    def _apply_transitions(
        self,
        clip_paths: list[str],
        transition_type: str
    ) -> list[str]:
        """Apply cross-dissolves or other transitions between clips"""
        pass
    
    def _normalize_audio_levels(self, video_path: str) -> str:
        """Normalize audio across clips to prevent volume jumps"""
        pass
    
    def _verify_output(self, output_path: str, expected_clip_count: int) -> bool:
        """Verify assembled video has correct clip count and plays properly"""
        pass
```

**FFmpeg assembly command pattern:**

```bash
# Simple concatenation (hard cuts)
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy output.mp4

# With re-encoding and audio normalization
ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c:v libx264 -preset medium -crf 18 \
  -af loudnorm \
  output.mp4
```

**concat_list.txt format:**

```
file '/absolute/path/to/clip_000.mp4'
file '/absolute/path/to/clip_001.mp4'
file '/absolute/path/to/clip_002.mp4'
```

**Transition options:**

- **cut** (default) - Hard cuts, fastest, no re-encoding needed
- **dissolve** - Cross-dissolve between clips (requires re-encoding, slower)
- **fade** - Fade to black between clips

For most scenes, hard cuts are fine. Dissolves are useful for time passage or location changes.

---

### 8. `assembly/scene_compiler.py`

**Purpose:** Compile all scenes into a complete novel video (optional final step).

**Class: `SceneCompiler`**

```python
class SceneCompiler:
    def __init__(self, assembler: ClipAssembler)
    
    def compile_novel(
        self,
        novel_id: str,
        scene_video_paths: list[str],
        output_path: str,
        add_title_card: bool = True
    ) -> CompilationResult
    
    def _create_title_card(
        self,
        novel_title: str,
        author: str,
        duration_seconds: int = 3
    ) -> str:
        """Generate title card video using FFmpeg drawtext filter"""
        pass
    
    def _add_chapter_markers(
        self,
        video_path: str,
        chapter_timecodes: list[tuple[str, float]]
    ) -> str:
        """Add chapter markers to MP4 metadata"""
        pass
```

---

### 9. `monitoring/progress_tracker.py`

**Purpose:** Real-time progress display during execution.

**Class: `ProgressTracker`**

```python
class ProgressTracker:
    def __init__(self, total_jobs: int)
    
    def start(self) -> None:
        """Initialize progress bar and metrics display"""
        pass
    
    def update(
        self,
        completed: int,
        failed: int,
        running: int,
        current_cost: float,
        estimated_time_remaining: int
    ) -> None:
        """Update progress display"""
        pass
    
    def log_job_complete(self, job_id: str, duration: float, cost: float) -> None:
        """Log individual job completion"""
        pass
    
    def finish(self, report: ExecutionReport) -> None:
        """Display final summary"""
        pass
```

**Display format (using `rich` library):**

```
Generating Videos - Novel: "The Detective's Last Case"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 47/100 47%

Status:
  Complete: 47  Running: 5  Failed: 2  Queued: 46
  
Costs:
  Estimated: $12.50  Actual: $5.85  Remaining: ~$6.65
  
Time:
  Elapsed: 18m 34s  Estimated Remaining: ~21m
  Average per clip: 23.7s
  
Current:
  [Scene 12, Clip 3] "INT. WAREHOUSE - NIGHT" (8s, 1080p)
```

---

### 10. Pydantic Models — Phase 4 Additions

```python
class JobStatus(BaseModel):
    status: str                 # "queued" | "processing" | "completed" | "failed"
    progress: int               # 0-100
    eta_seconds: int | None
    error: str | None

class PollResult(BaseModel):
    job_id: str
    status: str
    video_url: str | None
    error: str | None

class DownloadResult(BaseModel):
    success: bool
    file_path: str | None
    file_size_bytes: int | None
    error: str | None

class JobResult(BaseModel):
    success: bool
    file_path: str | None
    generation_time_seconds: float | None
    cost_usd: float | None
    error: str | None

class AssemblyResult(BaseModel):
    success: bool
    output_path: str | None
    clip_count: int
    total_duration_seconds: float | None
    ffmpeg_command: str | None
    error: str | None

class ExecutionReport(BaseModel):
    novel_id: str
    total_jobs: int
    completed: int
    failed: int
    skipped: int
    total_generation_time_seconds: float
    total_cost_usd: float
    average_cost_per_clip: float
    average_time_per_clip: float
    failed_job_ids: list[str]
    error_summary: dict[str, int]       # {error_type: count}

class RateLimits(BaseModel):
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int

class RateLimitStatus(BaseModel):
    provider: str
    current_minute: int
    current_hour: int
    current_day: int
    limits: RateLimits
    can_proceed: bool
    wait_seconds: int | None
```

---

## CLI Extensions

Add to `main.py`:

```
python main.py execute-queue --novel-id <uuid> [--resume] [--max-concurrent 5]
python main.py execute-single-job --job-id <uuid>
python main.py assemble-scene --scene-id <uuid>
python main.py assemble-all-scenes --novel-id <uuid>
python main.py compile-novel --novel-id <uuid> [--title-card]
python main.py status-queue --novel-id <uuid>
python main.py retry-failed --novel-id <uuid>
python main.py phase4 --novel-id <uuid> [--assemble] [--compile]    # Full pipeline
```

**`phase4` flow:**

1. Load job queue from Phase 3
2. Check API credentials are configured
3. Display execution plan (job count, estimated cost, estimated time)
4. Ask user to confirm execution
5. Initialize progress tracker
6. Execute job queue with concurrency and retry logic
7. Download all videos
8. If `--assemble`: assemble clips into scene videos
9. If `--compile`: compile scenes into complete novel video
10. Generate execution report
11. Print summary:
    - Clips generated: X/Y
    - Failed jobs: X (with error breakdown)
    - Total cost: $X.XX (estimated: $Y.YY)
    - Total time: Xh Ym
    - Output location: /path/to/scenes/

**Resume capability:**

```bash
# Start execution
python main.py phase4 --novel-id abc123

# Process crashes at clip 47/100...

# Resume from where it left off
python main.py phase4 --novel-id abc123 --resume
```

---

## Error Handling & Recovery

**Failure scenarios and recovery:**

| Scenario | Detection | Recovery Strategy |
|----------|-----------|-------------------|
| API rate limit hit | HTTP 429 response | Wait 60s, retry automatically |
| Single job timeout | Poll exceeds 5min | Mark failed, continue queue |
| Network failure mid-download | Incomplete file / checksum mismatch | Retry download up to 3x |
| Corrupted video file | FFprobe verification fails | Delete file, re-queue job |
| FFmpeg assembly fails | Non-zero exit code | Log error, manual review needed |
| Entire API service down | Multiple consecutive 503s | Pause queue, alert user |

**Manual intervention commands:**

```bash
# View all failed jobs for a novel
python main.py list-failures --novel-id <uuid>

# Retry specific failed job
python main.py retry-job --job-id <uuid>

# Retry all failed jobs for a novel
python main.py retry-failed --novel-id <uuid>

# Skip failed jobs and continue
python main.py skip-failed --novel-id <uuid>

# Export failed job details for debugging
python main.py export-failures --novel-id <uuid> --output failures.json
```

---

## Quality Gates

Before Phase 4 is considered complete:

- [ ] All jobs in queue attempted at least once
- [ ] Success rate >= 90% (some failures are acceptable)
- [ ] All downloaded videos pass FFprobe integrity check
- [ ] Actual cost within 20% of estimate
- [ ] All completed clips are correctly named and organized
- [ ] Scene assembly produces playable MP4 files
- [ ] No orphaned temp files remain in output directories

---

## Output Artifacts

After `phase4` completes:

1. **Individual clips** at `output/clips/<novel_id>/<scene_id>/clip_*.mp4`
2. **Assembled scenes** at `output/scenes/<novel_id>/scene_*.mp4`
3. **Complete novel video** (optional) at `output/final/<title>_complete.mp4`
4. **Execution report** saved to SQLite and exported as JSON
5. **Cost report** breaking down spend by scene and clip type
6. **Failed jobs log** for debugging and manual intervention

---

## Performance Optimizations

**Concurrency tuning:**

- Start with `max_concurrent_jobs=5`
- If API provider can handle more, increase to 10
- Monitor rate limit errors - if frequent, decrease concurrency
- Use `asyncio.Semaphore` to enforce concurrency limit

**Bandwidth optimization:**

- Download clips in parallel (separate from generation concurrency)
- Use `aiofiles` for async disk writes
- Stream large files rather than loading into memory
- Implement download resume (HTTP range requests) for interrupted transfers

**Storage optimization:**

- Compress clips after download if storage is limited (trade encoding time for disk space)
- Optionally delete individual clips after scene assembly
- Implement clip deduplication (check checksums before download)

**Cost optimization strategies:**

- Use lower resolution (720p) for testing/previews
- Generate only selected scenes initially
- Batch similar shots together (same location/characters)
- Use reference images aggressively to reduce regeneration needs

---

## Testing Strategy

**Unit tests:**

- Mock API responses for client tests
- Test retry logic with various error scenarios
- Test FFmpeg command generation
- Test file path construction and naming

**Integration tests:**

- Execute single job end-to-end with real API (small test account)
- Test download and verification flow
- Test scene assembly with sample clips
- Test resume capability (stop mid-queue, restart)

**Load tests:**

- Generate 100+ clips to verify queue stability
- Test concurrent job handling
- Verify rate limiter prevents throttling
- Measure peak memory usage during concurrent downloads

---

## Scope Boundaries

Phase 4 explicitly does NOT:

- Perform any video editing beyond assembly (no cuts, no effects)
- Add music or sound effects (use Seedance 2.0's native audio)
- Generate subtitles or captions
- Perform colour grading or post-processing
- Upload videos to hosting platforms (YouTube, Vimeo, etc.)
- Create thumbnails or promotional materials

These could be future enhancements but are out of scope for the core pipeline.

---

## Production Deployment Considerations

**Secrets management:**

```bash
# .env
SEEDANCE_API_KEY=your_seedance_key_here
KLING_API_KEY=your_kling_key_here
RUNWAYML_API_KEY=your_runway_key_here

# Never commit .env to git
# Use environment variables in production
```

**Monitoring and alerting:**

- Log all API calls with timestamp, cost, duration
- Alert on sustained high failure rate (>20%)
- Alert on unexpected cost spikes
- Monitor disk space (video files accumulate quickly)

**Backup strategy:**

- SQLite database contains all job state - back up regularly
- Consider generated clips disposable (can regenerate from queue)
- Store Story Bible and prompts in version control

**Cost controls:**

- Set hard cost limits in code (e.g. abort if spend exceeds $X)
- Require user confirmation before executing expensive queues
- Provide dry-run mode that shows cost without executing

---

## Final Integration Test

After building all 4 phases, run this end-to-end test:

```bash
# 1. Ingest a short novel (or single chapter for testing)
python main.py run-all --pdf test_novel.pdf

# 2. Convert to script
python main.py phase2 --novel-id <uuid>

# 3. Generate prompts
python main.py phase3 --novel-id <uuid> --api seedance

# 4. Execute first scene only (cost-effective test)
python main.py execute-queue --novel-id <uuid> --limit-scenes 1

# 5. Verify output
ls output/clips/<novel-id>/scene_001/
ls output/scenes/<novel-id>/scene_001.mp4

# 6. Play the video!
ffplay output/scenes/<novel-id>/scene_001.mp4
```

If scene 001 plays smoothly with coherent visuals and audio, the pipeline is working end-to-end.

---

*Build spec authored for Novel-to-Screen Pipeline, Phase 4.*  
*Prev: Phase 3 — Video Prompt Engineering*  
*Complete: Full novel-to-video pipeline*
