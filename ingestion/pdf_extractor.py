"""PDF text extraction module."""
import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import List
from utils.logger import setup_logger
from ingestion.models import ExtractedDocument
from ingestion.cleaner import clean_text, remove_headers_footers

logger = setup_logger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""
    pass


class PDFExtractor:
    """Extracts text from PDF novels."""
    
    def extract(self, pdf_path: str) -> ExtractedDocument:
        """Extract clean text from a PDF novel.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            ExtractedDocument with cleaned text and metadata
            
        Raises:
            PDFExtractionError: If extraction fails or PDF has no text
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise PDFExtractionError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"Extracting text from {pdf_path.name}")
        
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PDFExtractionError(f"Failed to open PDF: {e}")
        
        if doc.page_count == 0:
            raise PDFExtractionError("PDF has no pages")
        
        # Extract text from each page
        pages = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            pages.append(text)
        
        doc.close()
        
        # Check if PDF has extractable text
        total_text = ''.join(pages)
        if len(total_text.strip()) < 100:
            raise PDFExtractionError(
                "PDF appears to contain no extractable text. "
                "This may be a scanned image PDF. Please use an OCR'd version."
            )
        
        # Clean pages (remove headers/footers)
        pages = remove_headers_footers(pages)
        
        # Detect chapter boundaries
        chapter_boundaries = self._detect_chapter_boundaries(pages)
        
        # Combine all pages
        raw_text = '\n\n'.join(pages)
        raw_text = clean_text(raw_text)
        
        # Calculate word count
        word_count = len(raw_text.split())
        
        # Extract title (use filename if no title detected)
        title = pdf_path.stem
        
        logger.info(
            f"Extracted {len(pages)} pages, {word_count} words, "
            f"{len(chapter_boundaries)} chapters"
        )
        
        return ExtractedDocument(
            title=title,
            raw_text=raw_text,
            page_count=len(pages),
            chapter_boundaries=chapter_boundaries,
            metadata={
                'filename': pdf_path.name,
                'word_count': word_count,
                'file_path': str(pdf_path.absolute())
            }
        )
    
    def _detect_chapter_boundaries(self, pages: List[str]) -> List[int]:
        """Detect page indices where chapters start.
        
        Args:
            pages: List of page texts
            
        Returns:
            List of page indices (0-indexed)
        """
        chapter_pages = []
        
        # Patterns for chapter headings
        patterns = [
            r'^Chapter\s+\d+',
            r'^CHAPTER\s+\d+',
            r'^Chapter\s+[IVXLCDM]+',  # Roman numerals
            r'^\d+\.\s+',  # Numbered sections
            r'^Part\s+\d+',
            r'^PART\s+\d+',
        ]
        
        for page_num, page_text in enumerate(pages):
            # Check first few lines of each page
            lines = page_text.split('\n')[:5]
            
            for line in lines:
                line = line.strip()
                for pattern in patterns:
                    if re.match(pattern, line, re.IGNORECASE):
                        chapter_pages.append(page_num)
                        break
        
        # If no chapters detected, treat the whole document as one chapter
        if not chapter_pages:
            chapter_pages = [0]
        
        return chapter_pages
