# Novel-to-Screen Pipeline — Phase 1
## Novel Ingestion & Story Bible Extraction

**Version:** 1.0  
**Stack:** Python 3.11+  
**Storage:** SQLite + ChromaDB (local vector store)  
**Input:** PDF novels

---

## Overview

Phase 1 of the Novel-to-Screen pipeline converts PDF novels into structured Story Bibles — comprehensive databases of characters, locations, narrative tone, and world details that ensure consistency for downstream video generation.

### What It Does

1. **Ingests PDF novels** — Extracts clean text, handles chapter detection
2. **Chunks text** — Splits into meaningful narrative units with overlap
3. **Extracts Story Bible** — Uses Claude LLM to extract:
   - Character profiles (with detailed physical descriptions)
   - Locations (with cinematographic visual descriptions)
   - Narrative tone and style
   - Plot summary and themes
   - World-building rules
4. **Stores everything** — SQLite for structured data, ChromaDB for semantic search

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

### Quick Start — Full Pipeline

```bash
python main.py run-all --pdf path/to/novel.pdf
```

This will:
1. Extract text from the PDF
2. Chunk the narrative
3. Extract the Story Bible using Claude
4. Save everything to `./output/`

### Individual Commands

```bash
# Ingest only (no LLM calls)
python main.py ingest --pdf path/to/novel.pdf

# Extract Story Bible from an already-ingested novel
python main.py extract-bible --novel-id <uuid>

# View all processed novels
python main.py status

# Export Story Bible to custom location
python main.py export-bible --novel-id <uuid> --output my_bible.json
```

---

## Configuration

Edit `.env` to customize settings:

```
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-opus-4-5-20251101  # Use Opus for quality, Haiku for cost
CHUNK_SIZE_TOKENS=800
CHUNK_OVERLAP_TOKENS=100
DB_PATH=./output/pipeline.db
CHROMA_PATH=./output/chroma
```

---

## Output

After a successful run, you'll have:

1. **SQLite database** at `./output/pipeline.db`
2. **ChromaDB vector store** at `./output/chroma/`
3. **Story Bible JSON** at `./output/story_bibles/<title>.json`

The Story Bible JSON is the key deliverable and input for Phase 2.

---

## Story Bible Structure

```json
{
  "novel_title": "Example Novel",
  "extraction_date": "2026-02-17T12:00:00",
  "characters": [
    {
      "name": "Character Name",
      "physical_description": "Detailed visual description for video generation...",
      "role": "protagonist",
      ...
    }
  ],
  "locations": [
    {
      "name": "Location Name",
      "visual_description": "Cinematographic description...",
      ...
    }
  ],
  "tone": { "genre": [...], "mood": "...", "style_notes": "..." },
  "plot": { "logline": "...", "synopsis": "...", ... },
  "timeline": { "era": "...", "technology_level": "..." },
  "world_rules": [...],
  "visual_style_notes": "..."
}
```

---

## Cost Estimation

For a ~300-page novel using **Claude Opus**:
- **Input tokens:** ~500K-800K (~$4-6)
- **Output tokens:** ~50K-100K (~$2-4)
- **Total:** $6-10 per novel

Use **Claude Haiku** for lower-cost extraction (~$0.50-1 per novel).

---

## Testing

Sample data is included for testing:

```bash
# Test with sample PDF (if provided)
python main.py run-all --pdf sample_data/test_novel.pdf
```

---

## Project Structure

```
novel_pipeline/
├── main.py                      # CLI entry point
├── config.py                    # Configuration
├── requirements.txt             # Dependencies
├── ingestion/                   # PDF extraction & chunking
│   ├── pdf_extractor.py
│   ├── chunker.py
│   └── cleaner.py
├── extraction/                  # Story Bible extraction
│   ├── story_bible_extractor.py
│   ├── prompts.py
│   └── models.py
├── storage/                     # Database operations
│   ├── database.py
│   ├── vector_store.py
│   └── schema.sql
└── output/                      # Generated files
    ├── pipeline.db
    ├── chroma/
    └── story_bibles/
```

---

## Troubleshooting

### "PDF has no extractable text"
Your PDF may be a scanned image. Use an OCR'd version or run it through OCR software first.

### API Rate Limits
The pipeline includes automatic retry logic with exponential backoff. If you hit rate limits, the extraction will pause and retry automatically.

### Out of Memory
For very large novels (>1000 pages), you may need to increase the batch size or process in multiple sessions.

---

## Next Steps

**Phase 2:** Script Conversion & Scene Breakdown (coming soon)

The Story Bible from Phase 1 will be used to:
- Convert novel chapters into screenplay format
- Break down scenes for video generation
- Maintain character and location consistency

---

*Built for the Novel-to-Screen Pipeline project.*
