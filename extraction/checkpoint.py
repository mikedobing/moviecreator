"""Checkpointing system for Story Bible extraction."""
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ExtractionCheckpoint:
    """Manages checkpoints for Story Bible extraction."""
    
    def __init__(self, novel_id: str, checkpoint_dir: Path = Path("./output/checkpoints")):
        """Initialize checkpoint manager.
        
        Args:
            novel_id: Unique ID for the novel
            checkpoint_dir: Directory to store checkpoints
        """
        self.novel_id = novel_id
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / f"{novel_id}_checkpoint.json"
    
    def save(self, data: Dict[str, Any]) -> None:
        """Save checkpoint data.
        
        Args:
            data: Checkpoint data including stage and extracted components
        """
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Checkpoint saved: {data.get('stage', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def load(self) -> Optional[Dict[str, Any]]:
        """Load checkpoint data if exists.
        
        Returns:
            Checkpoint data or None if no checkpoint exists
        """
        if not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"✓ Checkpoint loaded: {data.get('stage', 'unknown')}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    def clear(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("Checkpoint cleared")
    
    def exists(self) -> bool:
        """Check if checkpoint exists."""
        return self.checkpoint_file.exists()
