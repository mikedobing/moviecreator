-- Phase 2 Database Schema: Screenplay and Scene Breakdown Tables

CREATE TABLE IF NOT EXISTS screenplays (
    id TEXT PRIMARY KEY,              -- UUID
    novel_id TEXT NOT NULL UNIQUE,
    fountain_text TEXT NOT NULL,      -- Full screenplay in Fountain format
    scene_count INTEGER,
    page_count_estimate INTEGER,      -- ~1 min per page rule of thumb
    created_at TEXT NOT NULL,
    model_used TEXT NOT NULL,
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS screenplay_scenes (
    id TEXT PRIMARY KEY,              -- UUID = scene_id
    screenplay_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    scene_number INTEGER NOT NULL,    -- Sequential, 1-indexed
    slug_line TEXT NOT NULL,          -- e.g. "INT. ABANDONED WAREHOUSE - NIGHT"
    location_name TEXT,               -- Normalised to Story Bible location name
    interior_exterior TEXT,           -- "INT" | "EXT" | "INT/EXT"
    time_of_day TEXT,                 -- "DAY" | "NIGHT" | "DAWN" | "DUSK" | "CONTINUOUS"
    action_lines TEXT NOT NULL,       -- The scene's action/description text
    dialogue_json TEXT,               -- JSON array of {character, line, parenthetical}
    characters_present TEXT,          -- JSON array of character names from Story Bible
    scene_type TEXT,                  -- "dialogue", "action", "transition", "montage"
    emotional_beat TEXT,              -- The narrative/emotional purpose of this scene
    source_chunk_ids TEXT,            -- JSON array of Phase 1 chunk_ids this came from
    FOREIGN KEY (screenplay_id) REFERENCES screenplays(id),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS scene_breakdowns (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL UNIQUE,
    novel_id TEXT NOT NULL,
    breakdown_json TEXT NOT NULL,     -- Full SceneBreakdown serialised as JSON
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);
