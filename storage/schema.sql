-- SQLite schema for Novel Pipeline

CREATE TABLE IF NOT EXISTS novels (
    id TEXT PRIMARY KEY,           -- UUID
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,       -- SHA256 — prevents re-processing same file
    page_count INTEGER,
    word_count INTEGER,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,           -- UUID = chunk_id
    novel_id TEXT NOT NULL,
    chapter_number INTEGER,
    chunk_index INTEGER,
    text TEXT NOT NULL,
    token_count INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS story_bibles (
    id TEXT PRIMARY KEY,           -- UUID
    novel_id TEXT NOT NULL UNIQUE,
    bible_json TEXT NOT NULL,      -- Full StoryBible serialised as JSON
    created_at TEXT NOT NULL,
    model_used TEXT NOT NULL,
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    novel_id TEXT,
    phase TEXT,                    -- "ingestion", "extraction", etc.
    status TEXT,                   -- "running", "complete", "failed"
    started_at TEXT,
    completed_at TEXT,
    error TEXT,
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_chunks_novel_id ON chunks(novel_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks(novel_id, chapter_number);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_novel ON pipeline_runs(novel_id);
CREATE INDEX IF NOT EXISTS idx_novels_hash ON novels(file_hash);
