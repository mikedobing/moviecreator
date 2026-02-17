"""Test chunker functionality."""
import pytest
from ingestion.chunker import NarrativeChunker
from ingestion.models import ExtractedDocument


def test_single_chunk():
    """Test that small document creates single chunk."""
    doc = ExtractedDocument(
        title="Test Novel",
        raw_text="This is a short test novel with only a few sentences. It should fit in one chunk.",
        page_count=1,
        chapter_boundaries=[0],
        metadata={}
    )
    
    chunker = NarrativeChunker(chunk_size=1000, overlap=100)
    chunks = chunker.chunk(doc)
    
    assert len(chunks) == 1
    assert chunks[0].chapter_number == 1
    assert chunks[0].chunk_index == 0


def test_multiple_chunks():
    """Test that large document gets split."""
    # Create a large text
    paragraph = "This is a paragraph. " * 50
    large_text = "\n\n".join([paragraph] * 20)
    
    doc = ExtractedDocument(
        title="Large Novel",
        raw_text=large_text,
        page_count=10,
        chapter_boundaries=[0],
        metadata={}
    )
    
    chunker = NarrativeChunker(chunk_size=800, overlap=100)
    chunks = chunker.chunk(doc)
    
    assert len(chunks) > 1
    
    # Check chunk IDs are unique
    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_token_counting():
    """Test that token counting works."""
    doc = ExtractedDocument(
        title="Test",
        raw_text="Hello world",
        page_count=1,
        chapter_boundaries=[0],
        metadata={}
    )
    
    chunker = NarrativeChunker()
    chunks = chunker.chunk(doc)
    
    assert chunks[0].token_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
