# Novel-to-Screen Pipeline — Phase 1 & 2
## Novel Ingestion, Story Bible Extraction, and Screenplay Conversion

**Version:** 2.0  
**Stack:** Python 3.11+  
**Storage:** SQLite + ChromaDB (local vector store)  
**Input:** PDF novels

---

## Overview

This is a complete pipeline that converts PDF novels into professional screenplay format with detailed scene breakdowns for video generation.

### Phase 1: Novel Ingestion & Story Bible Extraction

1. **Ingests PDF novels** — Extracts clean text, handles chapter detection
2. **Chunks text** — Splits into meaningful narrative units with overlap
3. **Extracts Story Bible** — Uses Claude LLM to extract:
   - Character profiles (with detailed physical descriptions)
   - Locations (with cinematographic visual descriptions)
   - Narrative tone and style
   - Plot summary and themes
   - World-building rules
4. **Stores everything** — SQLite for structured data, ChromaDB for semantic search

### Phase 2: Screenplay Conversion & Scene Breakdown

1. **Converts novel to screenplay** — Transforms prose into Fountain format
2. **Determines act structure** — Analyzes story for 4-act structure
3. **Generates scenes** — Creates screenplay scenes with proper formatting
4. **Creates scene breakdowns** — Detailed visual composition for video generation

---

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

---

## Usage

### Phase 1: Novel Ingestion & Story Bible

```bash
# Full Phase 1 pipeline
python main.py run-all --pdf path/to/novel.pdf

# Individual commands
python main.py ingest --pdf path/to/novel.pdf
python main.py extract-bible --novel-id <uuid>
python main.py list-novels
python main.py export-bible --novel-id <uuid>
```

### Phase 2: Screenplay Conversion

```bash
# Full Phase 2 pipeline (screenplay + scene breakdowns)
python main.py phase2 --novel-id <uuid>

# Individual commands
python main.py convert-script --novel-id <uuid>
python main.py breakdown-scenes --novel-id <uuid>
python main.py list-scenes --novel-id <uuid>
```

---

## Output

After running the full pipeline (Phase 1 + 2), you'll have:

### Phase 1 Outputs:
1. **SQLite database** at `./output/pipeline.db`
2. **ChromaDB vector store** at `./output/chroma/`
3. **Story Bible JSON** at `./output/story_bibles/<title>.json`

### Phase 2 Outputs:
1. **Fountain screenplay** at `./output/screenplays/<title>.fountain`
2. **Screenplay JSON** at `./output/screenplays/<title>_screenplay.json`
3. **Scene breakdowns** at `./output/scene_breakdowns/<title>_breakdown.json`

---

## Configuration

Edit `.env` to customize settings:

```
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-opus-4-5-20251101  # Use Opus for quality
CHUNK_SIZE_TOKENS=800
CHUNK_OVERLAP_TOKENS=100
OUTPUT_DIR=./output
```

---

## Project Structure

```
novel_pipeline/
├── main.py                      # CLI entry point
├── config.py                    # Configuration
├── requirements.txt             # Dependencies
├── ingestion/                   # Phase 1: PDF extraction & chunking
│   ├── pdf_extractor.py
│   ├── chunker.py
│   └── cleaner.py
├── extraction/                  # Phase 1: Story Bible extraction
│   ├── story_bible_extractor.py
│   ├── prompts.py
│   ├── models.py
│   └── checkpoint.py
├── screenplay/                  # Phase 2: Screenplay conversion
│   ├── converter.py
│   ├── formatter.py
│   ├── scene_breakdown.py
│   └── prompts.py
├── storage/                     # Database operations
│   ├── database.py
│   ├── vector_store.py
│   ├── schema.sql
│   └── schema_phase2.sql
└── output/                      # Generated files
    ├── pipeline.db
    ├── chroma/
    ├── story_bibles/
    ├── screenplays/
    └── scene_breakdowns/
```

---

## Cost Estimation

For a ~300-page novel using **Claude Opus**:

**Phase 1:**
- Input tokens: ~500K-800K (~$4-6)
- Output tokens: ~50K-100K (~$2-4)
- Total: $6-10 per novel

**Phase 2:**
- Input tokens: ~200K-400K (~$2-3)
- Output tokens: ~30K-60K (~$1-2)
- Total: $3-5 per novel

**Combined:** ~$9-15 per novel end-to-end

---

## Next Steps

**Phase 3:** Video Generation from Scene Breakdowns (planned)
- Use scene breakdown JSON to generate video clips
- Assemble clips into complete video novel/movie

---

*Built for the Novel-to-Screen Pipeline project.*

