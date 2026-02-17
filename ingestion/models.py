"""Pydantic models for ingestion module."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any


class ExtractedDocument(BaseModel):
    """Represents an extracted PDF document."""
    title: str
    raw_text: str
    page_count: int
    chapter_boundaries: List[int] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NarrativeChunk(BaseModel):
    """Represents a chunk of narrative text."""
    chunk_id: str
    novel_title: str
    chapter_number: int
    chunk_index: int
    text: str
    token_count: int
    start_char: int
    end_char: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            'id': self.chunk_id,
            'novel_id': '',  # Will be set by caller
            'chapter_number': self.chapter_number,
            'chunk_index': self.chunk_index,
            'text': self.text,
            'token_count': self.token_count,
            'start_char': self.start_char,
            'end_char': self.end_char
        }
