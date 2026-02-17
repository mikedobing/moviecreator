"""Fountain screenplay formatter."""
import json
from pathlib import Path
from typing import List

from utils.logger import setup_logger
from extraction.models import Screenplay, ScreenplayScene, DialogueLine

logger = setup_logger(__name__)


class FountainFormatter:
    """Formats screenplay scenes into Fountain format."""
    
    def format(self, screenplay: Screenplay) -> str:
        """Format complete screenplay as Fountain text.
        
        Args:
            screenplay: Complete Screenplay object
            
        Returns:
            Fountain formatted text
        """
        lines = []
        
        # Title page
        lines.append(f"Title: {screenplay.novel_title}")
        lines.append(f"Draft: Screenplay Adaptation")
        lines.append(f"Based on: {screenplay.novel_title}")
        lines.append("")
        lines.append("===")
        lines.append("")
        
        # Scenes
        for scene in screenplay.scenes:
            lines.append(self.format_scene(scene))
            lines.append("")
        
        return "\n".join(lines)
    
    def format_scene(self, scene: ScreenplayScene) -> str:
        """Format single scene as Fountain text."""
        lines = []
        
        # Slug line
        lines.append(self._format_slug_line(scene))
        lines.append("")
        
        # Action lines
        if scene.action_lines:
            lines.append(scene.action_lines)
            lines.append("")
        
        # Dialogue
        if scene.dialogue:
            lines.append(self._format_dialogue_block(scene.dialogue))
        
        return "\n".join(lines)
    
    def _format_slug_line(self, scene: ScreenplayScene) ->str:
        """Format scene heading (slug line)."""
        return scene.slug_line
    
    def _format_dialogue_block(self, dialogue: List[DialogueLine]) -> str:
        """Format dialogue blocks."""
        lines = []
        
        for dlg in dialogue:
            lines.append(f"                    {dlg.character.upper()}")
            if dlg.parenthetical:
                lines.append(f"          ({dlg.parenthetical})")
            lines.append(f"        {dlg.line}")
            lines.append("")
        
        return "\n".join(lines)
    
    def export_fountain_file(self, screenplay: Screenplay, output_path: str) -> None:
        """Export screenplay as .fountain file."""
        fountain_text = self.format(screenplay)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(fountain_text)
        
        logger.info(f"Exported Fountain screenplay to {output_path}")
    
    def export_json(self, screenplay: Screenplay, output_path: str) -> None:
        """Export screenplay as JSON."""
        screenplay_dict = screenplay.model_dump()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(screenplay_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported JSON screenplay to {output_path}")
