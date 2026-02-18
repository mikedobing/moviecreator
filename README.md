# Novel-to-Screen Pipeline
## End-to-End Video Generation from Text

**Version:** 4.0  
**Stack:** Python 3.11+  
**Storage:** SQLite + ChromaDB (local vector store)  
**Input:** PDF novels  
**Output:** Full video adaptation (MP4)

---

## Overview

This pipeline automates the conversion of a novel into a screen adaptation, handling every step from text analysis to final video assembly.

### Phase 1: Ingestion & Story Bible
- Ingests PDF novels and chunks text.
- Extracts a comprehensive **Story Bible** (characters, locations, lore) using Claude.

### Phase 2: Screenplay & Breakdown
- Converts narrative prose into a **Fountain screenplay**.
- Generates detailed **Scene Breakdowns** with visual descriptions for every scene.

### Phase 3: Prompt Engineering
- Engineer specific **Video Prompts** for each shot in a scene.
- Validates prompts for coherence, safety, and character consistency.
- Estimates generation costs before execution.

### Phase 4: Execution & Assembly
- **Executes video generation** using APIs (Seedance, Kling, etc.).
- Handles async polling, downloading, and rate limiting.
- **Assembles clips** into final scene videos using FFmpeg.

---

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env and add your keys:
# ANTHROPIC_API_KEY=...
# SEEDANCE_API_KEY=... (or other provider)
```

**System Requirements:**
- **FFmpeg** must be installed and in your system PATH.

---

## End-to-End Usage

To run the entire pipeline from PDF to Video for a specific novel:

```bash
# 1. Ingest PDF and extract Story Bible (Phase 1)
python main.py run-all --pdf path/to/novel.pdf

# Note the <novel-id> output at the end of this step!
# You will use it for all subsequent commands.

# 2. Convert to Screenplay & Breakdowns (Phase 2)
python main.py phase2 --novel-id <novel-id>

# 3. Generate Video Prompts & Job Queue (Phase 3)
python main.py phase3 --novel-id <novel-id> --api seedance

# 4. Execute Video Generation & Assembly (Phase 4)
python main.py phase4 --novel-id <novel-id>
```

---

## Detailed Commands

### Phase 1: Ingestion
```bash
python main.py ingest --pdf novel.pdf
python main.py extract-bible --novel-id <uuid>
```

### Phase 2: Screenplay
```bash
python main.py convert-script --novel-id <uuid>
python main.py breakdown-scenes --novel-id <uuid>
```

### Phase 3: Prompts
```bash
# Generate prompts and build job queue
python main.py phase3 --novel-id <uuid> --api seedance
```

### Phase 4: Execution
```bash
# dry run / execute queue
python main.py execute-queue --novel-id <uuid> --max-concurrent 5

# manual scene assembly (if needed)
python main.py assemble-scene --scene-id <uuid> --output scene_01.mp4
```

---

## Output Structure

```
output/
├── pipeline.db                 # Core database
├── story_bibles/               # Phase 1 JSON
├── screenplays/                # Phase 2 Fountain/JSON
├── scene_breakdowns/           # Phase 2 Detailed JSON
├── prompts/                    # Phase 3 Prompt JSON
├── jobs/                       # Phase 3 Job Queue
├── clips/                      # Phase 4 Raw Video Clips
│   └── <novel_id>/
│       └── <scene_id>/
│           ├── clip_001.mp4
│           └── clip_002.mp4
└── scenes/                     # Phase 4 Assembled Videos
    └── <novel_id>/
        └── scene_001.mp4
```

---

## Cost Estimation (Approximate)

**Text Processing (Phases 1-3):** ~$10-$20 per novel (using Claude Opus/Sonnet).

**Video Generation (Phase 4):**
- Varies wildly by provider and novel length.
- Approx. $0.10 - $0.30 per clip.
- A 90-minute movie might have ~1000-1500 clips.
- **Estimated Total:** $150 - $450 per full movie adaptation.

*Always run `python main.py phase3` first to see a detailed cost estimate for your specific screenplay before executing Phase 4.*

---

*Project: Novel-to-Screen Pipeline*
