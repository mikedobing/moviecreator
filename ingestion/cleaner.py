"""Text cleaning utilities."""
import re
from typing import List


def clean_text(text: str) -> str:
    """Clean extracted text by normalizing whitespace and fixing common issues.
    
    Args:
        text: Raw text from PDF
        
    Returns:
        Cleaned text
    """
    # Remove excessive whitespace while preserving paragraph breaks
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Fix hyphenated line breaks (words split across lines)
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # Normalize whitespace within lines
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def remove_headers_footers(pages: List[str]) -> List[str]:
    """Remove repeated headers and footers from pages.
    
    Args:
        pages: List of page texts
        
    Returns:
        Pages with headers/footers removed
    """
    if len(pages) < 3:
        return pages
    
    cleaned_pages = []
    
    for page_text in pages:
        lines = page_text.split('\n')
        
        if len(lines) < 3:
            cleaned_pages.append(page_text)
            continue
        
        # Remove likely headers (first 1-2 short lines)
        start_idx = 0
        for i in range(min(2, len(lines))):
            if len(lines[i].strip()) < 50:  # Short line likely header
                start_idx = i + 1
            else:
                break
        
        # Remove likely footers (last 1-2 short lines)
        end_idx = len(lines)
        for i in range(len(lines) - 1, max(len(lines) - 3, 0), -1):
            if len(lines[i].strip()) < 50:  # Short line likely footer or page number
                end_idx = i
            else:
                break
        
        # Re-join cleaned lines
        cleaned_text = '\n'.join(lines[start_idx:end_idx])
        cleaned_pages.append(cleaned_text)
    
    return cleaned_pages
