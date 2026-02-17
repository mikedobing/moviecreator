"""Configuration module for Novel Pipeline."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5-20251101")
LLM_TEMPERATURE = 0  # For structured extraction consistency

# Chunking Configuration
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "800"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "100"))
BATCH_SIZE = 10  # Number of chunks to process per LLM call (increased for faster processing)

# Storage Configuration
DB_PATH = Path(os.getenv("DB_PATH", "./output/pipeline.db"))
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", "./output/chroma"))

# Ensure output directories exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

# Embedding Configuration
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Rate Limiting
API_CALL_DELAY = 2.0  # Seconds between API calls (increased to avoid rate limits)
MAX_RETRIES = 3
RETRY_BACKOFF_MULTIPLIER = 2

# Output Paths
OUTPUT_DIR = Path("./output")
STORY_BIBLES_DIR = OUTPUT_DIR / "story_bibles"
CHUNKS_DIR = OUTPUT_DIR / "chunks"

# Ensure output directories exist
STORY_BIBLES_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
