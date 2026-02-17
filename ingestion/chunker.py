"""Narrative text chunking module."""
import uuid
import tiktoken
from typing import List
from utils.logger import setup_logger
from ingestion.models import ExtractedDocument, NarrativeChunk
import config

logger = setup_logger(__name__)


class NarrativeChunker:
    """Chunks narrative text into meaningful units for embedding."""
    
    def __init__(
        self,
        chunk_size: int = config.CHUNK_SIZE_TOKENS,
        overlap: int = config.CHUNK_OVERLAP_TOKENS
    ):
        """Initialize chunker.
        
        Args:
            chunk_size: Target chunk size in tokens
            overlap: Overlap size in tokens
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        # Initialize tokenizer (use cl100k_base as approximation)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        logger.info(f"Chunker initialized: {chunk_size} tokens, {overlap} overlap")
    
    def chunk(self, doc: ExtractedDocument) -> List[NarrativeChunk]:
        """Chunk the extracted document into narrative units.
        
        Args:
            doc: ExtractedDocument to chunk
            
        Returns:
            List of NarrativeChunks
        """
        logger.info(f"Chunking document: {doc.title}")
        
        all_chunks = []
        
        # Split text by chapter boundaries if available
        if doc.chapter_boundaries and len(doc.chapter_boundaries) > 1:
            chapters = self._split_by_chapter(doc.raw_text, doc.chapter_boundaries)
        else:
            chapters = [doc.raw_text]
        
        # Process each chapter
        global_char_offset = 0
        
        for chapter_num, chapter_text in enumerate(chapters, start=1):
            chapter_chunks = self._chunk_chapter(
                chapter_text,
                chapter_num,
                global_char_offset,
                doc.title
            )
            all_chunks.extend(chapter_chunks)
            global_char_offset += len(chapter_text)
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(chapters)} chapters")
        
        return all_chunks
    
    def _split_by_chapter(
        self,
        text: str,
        boundaries: List[int]
    ) -> List[str]:
        """Split text by chapter boundaries.
        
        This is a simplified version - in reality we'd need to map
        page numbers to character positions. For now, we'll split
        roughly by position in text.
        
        Args:
            text: Full document text
            boundaries: Chapter boundary page numbers
            
        Returns:
            List of chapter texts
        """
        # Simple approach: divide text proportionally
        # This is an approximation since we don't have exact page->char mapping
        chapters = []
        text_length = len(text)
        
        # If only one boundary, return whole text
        if len(boundaries) <= 1:
            return [text]
        
        # Otherwise split into sections
        # For simplicity, split by equal sections
        num_chapters = len(boundaries)
        chars_per_chapter = text_length // num_chapters
        
        for i in range(num_chapters):
            start = i * chars_per_chapter
            end = (i + 1) * chars_per_chapter if i < num_chapters - 1 else text_length
            chapters.append(text[start:end])
        
        return chapters
    
    def _chunk_chapter(
        self,
        chapter_text: str,
        chapter_num: int,
        start_offset: int,
        novel_title: str
    ) -> List[NarrativeChunk]:
        """Chunk a single chapter.
        
        Args:
            chapter_text: Chapter text
            chapter_num: Chapter number
            start_offset: Character offset in full text
            novel_title: Novel title
            
        Returns:
            List of chunks for this chapter
        """
        token_count = self._count_tokens(chapter_text)
        
        # If chapter fits in one chunk, return it
        if token_count <= self.chunk_size:
            return [
                NarrativeChunk(
                    chunk_id=str(uuid.uuid4()),
                    novel_title=novel_title,
                    chapter_number=chapter_num,
                    chunk_index=0,
                    text=chapter_text,
                    token_count=token_count,
                    start_char=start_offset,
                    end_char=start_offset + len(chapter_text)
                )
            ]
        
        # Chapter is too large, split at paragraph boundaries
        return self._split_oversized_chapter(
            chapter_text,
            chapter_num,
            start_offset,
            novel_title
        )
    
    def _split_oversized_chapter(
        self,
        chapter_text: str,
        chapter_num: int,
        start_offset: int,
        novel_title: str
    ) -> List[NarrativeChunk]:
        """Split a large chapter into chunks at paragraph boundaries.
        
        Args:
            chapter_text: Chapter text
            chapter_num: Chapter number
            start_offset: Character offset in full text
            novel_title: Novel title
            
        Returns:
            List of chunks
        """
        chunks = []
        paragraphs = chapter_text.split('\n\n')
        
        current_chunk = []
        current_tokens = 0
        current_char_start = start_offset
        chunk_index = 0
        
        for para in paragraphs:
            para_tokens = self._count_tokens(para)
            
            # If adding this paragraph exceeds chunk size, finalize current chunk
            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(
                    NarrativeChunk(
                        chunk_id=str(uuid.uuid4()),
                        novel_title=novel_title,
                        chapter_number=chapter_num,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        token_count=current_tokens,
                        start_char=current_char_start,
                        end_char=current_char_start + len(chunk_text)
                    )
                )
                
                # Start new chunk with overlap
                # Keep last paragraph for context
                if len(current_chunk) > 1:
                    overlap_text = current_chunk[-1]
                    overlap_tokens = self._count_tokens(overlap_text)
                    current_chunk = [overlap_text, para]
                    current_tokens = overlap_tokens + para_tokens
                    current_char_start += len('\n\n'.join(current_chunk[:-1])) + 2
                else:
                    current_chunk = [para]
                    current_tokens = para_tokens
                    current_char_start += len(chunk_text) + 2
                
                chunk_index += 1
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append(
                NarrativeChunk(
                    chunk_id=str(uuid.uuid4()),
                    novel_title=novel_title,
                    chapter_number=chapter_num,
                    chunk_index=chunk_index,
                    text=chunk_text,
                    token_count=current_tokens,
                    start_char=current_char_start,
                    end_char=current_char_start + len(chunk_text)
                )
            )
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            Token count
        """
        return len(self.tokenizer.encode(text))
