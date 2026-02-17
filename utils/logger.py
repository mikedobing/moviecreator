"""Logging utilities for the pipeline."""
import logging
from rich.logging import RichHandler
from rich.console import Console

console = Console()

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with rich formatting.
    
    Args:
        name: Logger name
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding multiple handlers
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            console=console,
            show_time=True,
            show_path=False
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    
    return logger
