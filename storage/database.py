"""SQLite database operations for the pipeline."""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from utils.logger import setup_logger
import config

logger = setup_logger(__name__)


class Database:
    """Manages SQLite database operations."""
    
    def __init__(self, db_path: Path = config.DB_PATH):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Create tables if they don't exist."""
        # Load Phase 1 schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Load Phase 2 schema
        schema_phase2_path = Path(__file__).parent / "schema_phase2.sql"
        if schema_phase2_path.exists():
            with open(schema_phase2_path, 'r') as f:
                schema_phase2_sql = f.read()
            schema_sql += "\n" + schema_phase2_sql
        
        # Load Phase 3 schema
        schema_phase3_path = Path(__file__).parent / "schema_phase3.sql"
        if schema_phase3_path.exists():
            with open(schema_phase3_path, 'r') as f:
                schema_phase3_sql = f.read()
            schema_sql += "\n" + schema_phase3_sql
        
        with self._get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_novel(
        self,
        title: str,
        file_path: str,
        file_hash: str,
        page_count: int,
        word_count: int
    ) -> str:
        """Insert a new novel record.
        
        Args:
            title: Novel title
            file_path: Path to PDF file
            file_hash: SHA256 hash of file
            page_count: Number of pages
            word_count: Word count
            
        Returns:
            Novel UUID
        """
        novel_id = str(uuid.uuid4())
        ingested_at = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO novels (id, title, file_path, file_hash, page_count, word_count, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (novel_id, title, file_path, file_hash, page_count, word_count, ingested_at)
            )
            conn.commit()
        
        logger.info(f"Inserted novel: {title} (ID: {novel_id})")
        return novel_id
    
    def get_novel_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if a novel with this hash already exists.
        
        Args:
            file_hash: SHA256 hash of file
            
        Returns:
            Novel record dict or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM novels WHERE file_hash = ?",
                (file_hash,)
            ).fetchone()
            
            return dict(row) if row else None
    
    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Bulk insert narrative chunks.
        
        Args:
            chunks: List of chunk dictionaries
        """
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO chunks (id, novel_id, chapter_number, chunk_index, text, token_count, start_char, end_char)
                VALUES (:id, :novel_id, :chapter_number, :chunk_index, :text, :token_count, :start_char, :end_char)
                """,
                chunks
            )
            conn.commit()
        
        logger.info(f"Inserted {len(chunks)} chunks")
    
    def get_chunks(self, novel_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a novel.
        
        Args:
            novel_id: Novel UUID
            
        Returns:
            List of chunk dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE novel_id = ? ORDER BY chapter_number, chunk_index",
                (novel_id,)
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def insert_story_bible(
        self,
        novel_id: str,
        bible_dict: Dict[str, Any],
        model_used: str
    ) -> str:
        """Insert a Story Bible record.
        
        Args:
            novel_id: Novel UUID
            bible_dict: Story Bible as dictionary
            model_used: LLM model name used for extraction
            
        Returns:
            Story Bible UUID
        """
        bible_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        bible_json = json.dumps(bible_dict, indent=2)
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO story_bibles (id, novel_id, bible_json, created_at, model_used)
                VALUES (?, ?, ?, ?, ?)
                """,
                (bible_id, novel_id, bible_json, created_at, model_used)
            )
            conn.commit()
        
        logger.info(f"Inserted Story Bible for novel {novel_id}")
        return bible_id
    
    def get_story_bible(self, novel_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve Story Bible for a novel.
        
        Args:
            novel_id: Novel UUID
            
        Returns:
            Story Bible dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT bible_json FROM story_bibles WHERE novel_id = ?",
                (novel_id,)
            ).fetchone()
            
            if row:
                json_str = row['bible_json']
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode bible_json for novel {novel_id}")
                    logger.error(f"Error: {e}")
                    logger.error(f"Content length: {len(json_str) if json_str else 0}")
                    if json_str:
                         logger.error(f"First 100 chars: {json_str[:100]}")
                    raise
            return None
    
    def insert_pipeline_run(
        self,
        novel_id: str,
        phase: str,
        status: str = "running"
    ) -> str:
        """Insert a pipeline run record.
        
        Args:
            novel_id: Novel UUID
            phase: Pipeline phase name
            status: Initial status
            
        Returns:
            Pipeline run UUID
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_runs (id, novel_id, phase, status, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, novel_id, phase, status, started_at)
            )
            conn.commit()
        
        return run_id
    
    def update_pipeline_run(
        self,
        run_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Update pipeline run status.
        
        Args:
            run_id: Pipeline run UUID
            status: New status
            error: Error message if failed
        """
        completed_at = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE pipeline_runs
                SET status = ?, completed_at = ?, error = ?
                WHERE id = ?
                """,
                (status, completed_at, error, run_id)
            )
            conn.commit()
    
    def get_all_novels(self) -> List[Dict[str, Any]]:
        """Get all processed novels.
        
        Returns:
            List of novel dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM novels ORDER BY ingested_at DESC").fetchall()
            return [dict(row) for row in rows]
