-- schema_phase3.sql
-- Phase 3: Video Prompt Engineering & Generation Orchestration

CREATE TABLE IF NOT EXISTS video_prompts (
    id TEXT PRIMARY KEY,                    -- UUID = prompt_id
    scene_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    clip_index INTEGER NOT NULL,            -- Position within scene (0-indexed)
    prompt_type TEXT NOT NULL,              -- "establishing" | "action" | "dialogue" | "transition" | "reaction"
    prompt_text TEXT NOT NULL,              -- The actual prompt for the video API
    negative_prompt TEXT,                   -- What NOT to generate
    duration_seconds INTEGER NOT NULL,      -- Target clip length (4-15s)
    aspect_ratio TEXT DEFAULT '16:9',       -- "16:9" | "9:16" | "1:1"
    motion_intensity TEXT DEFAULT 'medium', -- "low" | "medium" | "high"
    camera_movement TEXT,                   -- "static" | "pan" | "tilt" | "dolly" | "handheld"
    reference_image_path TEXT,              -- Path to reference image (if used)
    character_consistency_tags TEXT,        -- JSON array of character appearance anchors
    audio_prompt TEXT,                      -- Audio generation guidance
    generation_params TEXT,                 -- JSON object of API-specific parameters
    estimated_cost_usd REAL,               -- Pre-computed cost estimate
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,                    -- UUID = job_id
    prompt_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    clip_index INTEGER NOT NULL,
    status TEXT DEFAULT 'queued',           -- "queued" | "running" | "complete" | "failed" | "skipped"
    api_provider TEXT NOT NULL,             -- "seedance" | "kling" | "runwayml"
    api_job_id TEXT,                        -- Provider's job ID (set in Phase 4)
    output_video_path TEXT,                 -- Path to generated video (set in Phase 4)
    generation_time_seconds INTEGER,        -- Actual generation time (set in Phase 4)
    actual_cost_usd REAL,                  -- Actual cost (set in Phase 4)
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (prompt_id) REFERENCES video_prompts(id)
);

CREATE TABLE IF NOT EXISTS prompt_iterations (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    clip_index INTEGER NOT NULL,
    iteration INTEGER NOT NULL,             -- Version number of this prompt
    prompt_text TEXT NOT NULL,
    notes TEXT,                             -- Why this iteration was created
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id)
);
