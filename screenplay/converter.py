"""Screenplay converter - converts novel chunks to screenplay scenes."""
import json
import time
import uuid
import re
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from pathlib import Path

from utils.logger import setup_logger
from storage.database import Database
from storage.vector_store import VectorStore
from extraction.models import (
    StoryBible,
    CharacterProfile,
    Location,
    ScreenplayScene,
    ActStructure,
    Screenplay,
    DialogueLine
)
from ingestion.models import NarrativeChunk
from screenplay import prompts
import config

logger = setup_logger(__name__)


class ScreenplayCheckpoint:
    """Manages checkpoints for screenplay conversion."""
    
    def __init__(self, novel_id: str, checkpoint_dir: Path = Path("./output/checkpoints")):
        """Initialize checkpoint manager."""
        self.novel_id = novel_id
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / f"{novel_id}_screenplay_checkpoint.json"
    
    def save(self, data: Dict[str, Any]) -> None:
        """Save checkpoint data."""
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Screenplay checkpoint saved: {data.get('stage', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to save screenplay checkpoint: {e}")
    
    def load(self) -> Optional[Dict[str, Any]]:
        """Load checkpoint data if exists."""
        if not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"✓ Screenplay checkpoint loaded: {data.get('stage', 'unknown')}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load screenplay checkpoint: {e}")
            return None
    
    def clear(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("Screenplay checkpoint cleared")


class ScreenplayConverter:
    """Converts novel chunks to screenplay format."""
    
    def __init__(
        self,
        anthropic_client: Anthropic,
        db: Database,
        vector_store: VectorStore,
        model: str = config.ANTHROPIC_MODEL
    ):
        """Initialize converter.
        
        Args:
            anthropic_client: Anthropic API client
            db: Database instance
            vector_store: Vector store instance
            model: Model name to use
        """
        self.client = anthropic_client
        self.db = db
        self.vector_store = vector_store
        self.model = model
        self.total_tokens_used = 0
        
        logger.info(f"ScreenplayConverter initialized with model: {model}")
    
    def convert(
        self,
        novel_id: str,
        use_checkpoints: bool = True
    ) -> Screenplay:
        """Convert novel to screenplay.
        
        Args:
            novel_id: Novel UUID
            use_checkpoints: Whether to use checkpointing
            
        Returns:
            Complete Screenplay
        """
        logger.info(f"Starting screenplay conversion for novel {novel_id}")
        
        # Initialize checkpoint
        checkpoint = None
        checkpoint_data = None
        if use_checkpoints:
            checkpoint = ScreenplayCheckpoint(novel_id)
            checkpoint_data = checkpoint.load()
            
            if checkpoint_data:
                logger.info(f"📁 Found checkpoint at stage: {checkpoint_data.get('stage', 'unknown')}")
        
        # Load Story Bible and chunks
        story_bible_dict = self.db.get_story_bible(novel_id)
        if not story_bible_dict:
            raise ValueError(f"No Story Bible found for novel {novel_id}. Run Phase 1 first.")
        
        story_bible = StoryBible(**story_bible_dict)
        chunks = self._load_chunks_sequential(novel_id)
        
        if not chunks:
            raise ValueError(f"No chunks found for novel {novel_id}")
        
        logger.info(f"Loaded Story Bible and {len(chunks)} chunks")
        
        # Determine act structure
        if checkpoint_data and 'act_structure' in checkpoint_data:
            logger.info("✓ Loading act structure from checkpoint...")
            act_structure = ActStructure(**checkpoint_data['act_structure'])
        else:
            logger.info("Determining act structure...")
            act_structure = self._determine_act_structure(story_bible, len(chunks))
            
            if checkpoint:
                checkpoint.save({
                    'stage': 'act_structure_complete',
                    'act_structure': act_structure.model_dump()
                })
        
        # Convert chunks to scenes
        if checkpoint_data and 'scenes' in checkpoint_data:
            logger.info(f"✓ Loading {len(checkpoint_data['scenes'])} scenes from checkpoint...")
            scenes = [ScreenplayScene(**s) for s in checkpoint_data['scenes']]
            start_chunk_idx = checkpoint_data.get('last_processed_chunk_idx', 0) + 1
        else:
            scenes = []
            start_chunk_idx = 0
        
        logger.info(f"Converting chunks to screenplay scenes (starting from chunk {start_chunk_idx})...")
        
        # Process in overlapping batches of 3
        batch_size = 3
        scene_number = len(scenes) + 1
        
        for i in range(start_chunk_idx, len(chunks), 1):  # Move 1 chunk at a time
            # Get batch: previous, current, next (if available)
            batch_chunks = []
            batch_start = max(0, i - 1)
            batch_end = min(len(chunks), i + 2)
            
            for j in range(batch_start, batch_end):
                batch_chunks.append(chunks[j])
            
            # Determine act position
            act_position = self._get_act_position(i, act_structure)
            
            # Context description
            scene_context = f"Chunk {i+1}/{len(chunks)} ({act_position})"
            
            # Previous scene for continuity
            previous_scene = scenes[-1].model_dump() if scenes else None
            
            # Convert batch to scenes
            new_scenes = self._convert_chunk_batch_to_scenes(
                batch_chunks,
                story_bible,
                previous_scene,
                act_position,
                scene_context,
                scene_number
            )
            
            # Add scenes
            for scene in new_scenes:
                scenes.append(scene)
                scene_number += 1
            
            # Save checkpoint every 10 chunks
            if checkpoint and (i + 1) % 10 == 0:
                checkpoint.save({
                    'stage': f'scenes_through_chunk_{i}',
                    'scenes': [s.model_dump() for s in scenes],
                    'act_structure': act_structure.model_dump(),
                    'last_processed_chunk_idx': i,
                    'tokens_used': self.total_tokens_used
                })
            
            # Rate limiting
            time.sleep(config.API_CALL_DELAY)
        
        # Renumber scenes
        scenes = self._renumber_scenes(scenes)
        
        # Create screenplay
        screenplay_id = str(uuid.uuid4())
        screenplay = Screenplay(
            screenplay_id=screenplay_id,
            novel_id=novel_id,
            novel_title=story_bible.novel_title,
            scenes=scenes,
            act_structure=act_structure,
            fountain_text="",  # Will be set by formatter
            scene_count=len(scenes),
            page_count_estimate=self._estimate_page_count(scenes),
            model_used=self.model
        )
        
        # Clear checkpoint on success
        if checkpoint:
            checkpoint.clear()
        
        logger.info(f"Screenplay conversion complete: {len(scenes)} scenes, ~{screenplay.page_count_estimate} pages")
        logger.info(f"Total tokens used: {self.total_tokens_used:,}")
        
        return screenplay
    
    def _load_chunks_sequential(self, novel_id: str) -> List[NarrativeChunk]:
        """Load chunks in sequential order."""
        chunk_dicts = self.db.get_chunks(novel_id)
        
        chunks = [
            NarrativeChunk(
                chunk_id=c['id'],
                novel_title=c.get('novel_title', ''),
                chapter_number=c['chapter_number'],
                chunk_index=c['chunk_index'],
                text=c['text'],
                token_count=c['token_count'],
                start_char=c['start_char'],
                end_char=c['end_char']
            )
            for c in chunk_dicts
        ]
        
        return chunks
    
    def _determine_act_structure(
        self,
        story_bible: StoryBible,
        chunk_count: int
    ) -> ActStructure:
        """Determine act boundaries using LLM.
        
        Returns:
            ActStructure with chunk ranges
        """
        prompt = prompts.act_structure_prompt(
            story_bible.plot.model_dump(),
            chunk_count
        )
        
        result = self._call_llm(prompt, expect_json=True)
        act_data = json.loads(result)
        
        # Convert lists to tuples
        return ActStructure(
            act_one_chunk_range=tuple(act_data['act_one_chunk_range']),
            act_two_a_chunk_range=tuple(act_data['act_two_a_chunk_range']),
            act_two_b_chunk_range=tuple(act_data['act_two_b_chunk_range']),
            act_three_chunk_range=tuple(act_data['act_three_chunk_range'])
        )
    
    def _get_act_position(self, chunk_idx: int, act_structure: ActStructure) -> str:
        """Determine which act a chunk index falls into."""
        if act_structure.act_one_chunk_range[0] <= chunk_idx <= act_structure.act_one_chunk_range[1]:
            return "Act 1"
        elif act_structure.act_two_a_chunk_range[0] <= chunk_idx <= act_structure.act_two_a_chunk_range[1]:
            return "Act 2A"
        elif act_structure.act_two_b_chunk_range[0] <= chunk_idx <= act_structure.act_two_b_chunk_range[1]:
            return "Act 2B"
        else:
            return "Act 3"
    
    def _convert_chunk_batch_to_scenes(
        self,
        chunks: List[NarrativeChunk],
        story_bible: StoryBible,
        previous_scene: Optional[Dict[str, Any]],
        act_position: str,
        scene_context: str,
        starting_scene_number: int
    ) -> List[ScreenplayScene]:
        """Convert a batch of chunks to screenplay scenes using LLM."""
        chunk_texts = [chunk.text for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        
        prompt = prompts.novel_to_scene_prompt(
            chunk_texts,
            story_bible.model_dump(),
            scene_context,
            previous_scene,
            act_position
        )
        
        # Call LLM
        fountain_text = self._call_llm(prompt, expect_json=False)
        
        # Parse Fountain to scenes
        scenes = self._parse_fountain_to_scenes(
            fountain_text,
            starting_scene_number,
            chunk_ids,
            story_bible
        )
        
        return scenes
    
    def _parse_fountain_to_scenes(
        self,
        fountain_text: str,
        starting_scene_number: int,
        source_chunk_ids: List[str],
        story_bible: StoryBible
    ) -> List[ScreenplayScene]:
        """Parse Fountain format text into ScreenplayScene objects."""
        scenes = []
        current_scene_number = starting_scene_number
        
        # Split by scene headings (slug lines)
        # Fountain slug lines are all caps and match: INT/EXT LOCATION - TIME
        slug_pattern = r'^(INT\.|EXT\.|INT\./EXT\.|I/E\.) (.+?) - (.+?)$'
        
        lines = fountain_text.strip().split('\n')
        current_scene_lines = []
        current_slug = None
        
        for line in lines:
            line = line.strip()
            
            # Check if this is a slug line
            if re.match(slug_pattern, line, re.IGNORECASE):
                # Save previous scene if exists
                if current_slug and current_scene_lines:
                    scene = self._build_scene_from_lines(
                        current_slug,
                        current_scene_lines,
                        current_scene_number,
                        source_chunk_ids,
                        story_bible
                    )
                    if scene:
                        scenes.append(scene)
                        current_scene_number += 1
                
                # Start new scene
                current_slug = line
                current_scene_lines = []
            else:
                if current_slug:  # Only collect lines if we have a slug
                    current_scene_lines.append(line)
        
        # Don't forget the last scene
        if current_slug and current_scene_lines:
            scene = self._build_scene_from_lines(
                current_slug,
                current_scene_lines,
                current_scene_number,
                source_chunk_ids,
                story_bible
            )
            if scene:
                scenes.append(scene)
        
        return scenes
    
    def _build_scene_from_lines(
        self,
        slug_line: str,
        scene_lines: List[str],
        scene_number: int,
        source_chunk_ids: List[str],
        story_bible: StoryBible
    ) -> Optional[ScreenplayScene]:
        """Build a ScreenplayScene from Fountain lines."""
        # Parse slug line
        slug_pattern = r'^(INT\.|EXT\.|INT\./EXT\.|I/E\.) (.+?) - (.+?)$'
        match = re.match(slug_pattern, slug_line, re.IGNORECASE)
        
        if not match:
            logger.warning(f"Could not parse slug line: {slug_line}")
            return None
        
        int_ext = match.group(1).strip().upper()
        location_name = match.group(2).strip()
        time_of_day = match.group(3).strip().upper()
        
        # Separate action and dialogue
        action_lines = []
        dialogue_blocks = []
        characters_mentioned = set()
        
        i = 0
        while i < len(scene_lines):
            line = scene_lines[i]
            
            # Check if this is a character cue (ALL CAPS, not a transition)
            if line.isupper() and line and not line.endswith(':') and len(line.split()) < 5:
                # This is likely a character name
                character = line.strip()
                i += 1
                
                # Next line might be a parenthetical
                parenthetical = None
                if i < len(scene_lines) and scene_lines[i].startswith('(') and scene_lines[i].endswith(')'):
                    parenthetical = scene_lines[i].strip('()')
                    i += 1
                
                # Collect dialogue lines until we hit an empty line or next character
                dialogue_lines = []
                while i < len(scene_lines):
                    if not scene_lines[i] or scene_lines[i].isupper():
                        break
                    dialogue_lines.append(scene_lines[i])
                    i += 1
                
                if dialogue_lines:
                    dialogue_blocks.append(DialogueLine(
                        character=character,
                        line=' '.join(dialogue_lines),
                        parenthetical=parenthetical
                    ))
                    characters_mentioned.add(character)
            else:
                # Action line
                if line:
                    action_lines.append(line)
                i += 1
        
        # Extract characters from action lines (simple: look for names from Story Bible)
        action_text = ' '.join(action_lines)
        for char in story_bible.characters:
            if char.name in action_text or char.name.upper() in action_text:
                characters_mentioned.add(char.name)
        
        # Determine scene type
        scene_type = "dialogue" if dialogue_blocks else "action"
        
        # Emotional beat (simple heuristic from first action line)
        emotional_beat = action_lines[0] if action_lines else "Scene progression"
        
        return ScreenplayScene(
            scene_id=str(uuid.uuid4()),
            scene_number=scene_number,
            slug_line=slug_line,
            interior_exterior=int_ext,
            location_name=location_name,
            time_of_day=time_of_day,
            action_lines='\n'.join(action_lines),
            dialogue=dialogue_blocks,
            characters_present=list(characters_mentioned),
            scene_type=scene_type,
            emotional_beat=emotional_beat,
            adaptation_notes=[],
            source_chunk_ids=source_chunk_ids
        )
    
    def _renumber_scenes(self, scenes: List[ScreenplayScene]) -> List[ScreenplayScene]:
        """Renumber scenes sequentially."""
        for i, scene in enumerate(scenes, start=1):
            scene.scene_number = i
        return scenes
    
    def _estimate_page_count(self, scenes: List[ScreenplayScene]) -> int:
        """Estimate screenplay page count (rough: 55 lines per page)."""
        total_lines = 0
        for scene in scenes:
            total_lines += 2  # Slug line + blank
            total_lines += len(scene.action_lines.split('\n'))
            total_lines += len(scene.dialogue) * 4  # Character, dialogue, spacing
        
        return max(1, total_lines // 55)
    
    def _call_llm(self, prompt: str, expect_json: bool = False) -> str:
        """Call Anthropic API with retry logic (reuse from Phase 1)."""
        max_retries = 10
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=8192,  # Longer for screenplay scenes
                    temperature=config.LLM_TEMPERATURE,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                self.total_tokens_used += message.usage.input_tokens + message.usage.output_tokens
                response_text = message.content[0].text
                
                # JSON extraction if needed
                if expect_json:
                    try:
                        json.loads(response_text)
                        return response_text
                    except json.JSONDecodeError:
                        # Try to extract from code blocks
                        if "```json" in response_text:
                            parts = response_text.split("```json")
                            if len(parts) > 1:
                                extracted = parts[1].split("```")[0].strip()
                                json.loads(extracted)  # Validate
                                return extracted
                        elif "```" in response_text:
                            parts = response_text.split("```")
                            if len(parts) >= 3:
                                extracted = parts[1].strip()
                                json.loads(extracted)
                                return extracted
                        
                        # Try finding JSON object/array
                        start = response_text.find('{') if '{' in response_text else response_text.find('[')
                        if start != -1:
                            end_char = '}' if response_text[start] == '{' else ']'
                            end = response_text.rfind(end_char)
                            if end != -1:
                                extracted = response_text[start:end+1]
                                json.loads(extracted)
                                return extracted
                        
                        logger.error(f"Could not extract JSON. First 500 chars: {response_text[:500]}")
                        raise json.JSONDecodeError("Could not extract JSON", response_text, 0)
                
                return response_text
                
            except Exception as e:
                is_overload = "overloaded_error" in str(e) or "529" in str(e)
                is_rate_limit = "rate_limit_error" in str(e) or "429" in str(e)
                
                if is_overload or is_rate_limit:
                    wait_time = min(base_delay * (2 ** attempt), 60)
                    if attempt < max_retries - 1:
                        logger.warning(f"{'Overload' if is_overload else 'Rate limit'} error. Waiting {wait_time:.1f}s")
                        time.sleep(wait_time)
                        continue
                else:
                    if attempt < 3:
                        wait_time = base_delay * (attempt + 1)
                        logger.warning(f"API error: {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                
                logger.error(f"LLM call failed: {e}")
                raise
        
        raise Exception(f"LLM call failed after {max_retries} retries")
