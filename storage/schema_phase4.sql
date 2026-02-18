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
