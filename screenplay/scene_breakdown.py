"""Scene breakdown extractor for Phase 3 video generation."""
import json
import time
import uuid
from typing import List, Dict, Any

from anthropic import Anthropic
from utils.logger import setup_logger
from storage.database import Database
from extraction.models import (
    StoryBible,
    ScreenplayScene,
    SceneBreakdown,
    VisualComposition
)
from screenplay import prompts
import config

logger = setup_logger(__name__)


class SceneBreakdownExtractor:
    """Extracts detailed scene breakdowns for video generation."""
    
    def __init__(
        self,
        anthropic_client: Anthropic,
        db: Database,
        model: str = config.ANTHROPIC_MODEL
    ):
        """Initialize extractor."""
        self.client = anthropic_client
        self.db = db
        self.model = model
        self.total_tokens_used = 0
        
        logger.info(f"SceneBreakdownExtractor initialized")
    
    def process_all_scenes(
        self,
        scenes: List[ScreenplayScene],
        story_bible: StoryBible
    ) -> List[SceneBreakdown]:
        """Process all scenes to generate breakdowns.
        
        Args:
            scenes: List of screenplay scenes
            story_bible: Complete Story Bible
            
        Returns:
            List of scene breakdowns
        """
        breakdowns = []
        
        for scene in scenes:
            logger.info(f"Processing scene {scene.scene_number}/{len(scenes)}: {scene.slug_line}")
            
            breakdown = self.process_scene(scene, story_bible)
            breakdowns.append(breakdown)
            
            # Rate limiting
            time.sleep(config.API_CALL_DELAY)
        
        logger.info(f"Completed {len(breakdowns)} scene breakdowns")
        return breakdowns
    
    def process_scene(
        self,
        scene: ScreenplayScene,
        story_bible: StoryBible
    ) -> SceneBreakdown:
        """Process single scene to generate breakdown."""
        prompt = prompts.scene_breakdown_prompt(
            scene.model_dump(),
            story_bible.model_dump()
        )
        
        result = self._call_llm(prompt)
        breakdown_data = json.loads(result)
        
        # Build SceneBreakdown
        breakdown = SceneBreakdown(
            breakdown_id=str(uuid.uuid4()),
            scene_id=scene.scene_id,
            scene_number=scene.scene_number,
            slug_line=scene.slug_line,
            emotional_beat=breakdown_data.get('emotional_beat', scene.emotional_beat),
            narrative_purpose=breakdown_data.get('narrative_purpose', ''),
            composition=VisualComposition(**breakdown_data.get('composition', {})),
            characters_with_descriptions=breakdown_data.get('characters_with_descriptions', {}),
            location_visual_description=breakdown_data.get('location_visual_description', ''),
            props_and_set_dressing=breakdown_data.get('props_and_set_dressing', []),
            ambient_sound=breakdown_data.get('ambient_sound', ''),
            dialogue_present=breakdown_data.get('dialogue_present', len(scene.dialogue) > 0),
            music_mood=breakdown_data.get('music_mood', ''),
            special_requirements=breakdown_data.get('special_requirements', []),
            estimated_clip_count=breakdown_data.get('estimated_clip_count', 1),
            continuity_notes=breakdown_data.get('continuity_notes', ''),
            prompt_ready=breakdown_data.get('prompt_ready', True)
        )
        
        return breakdown
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM with retry logic."""
        max_retries = 10
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=config.LLM_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                self.total_tokens_used += message.usage.input_tokens + message.usage.output_tokens
                response_text = message.content[0].text
                
                # Extract JSON
                try:
                    json.loads(response_text)
                    return response_text
                except json.JSONDecodeError:
                    if "```json" in response_text:
                        extracted = response_text.split("```json")[1].split("```")[0].strip()
                        json.loads(extracted)
                        return extracted
                    elif "```" in response_text:
                        parts = response_text.split("```")
                        if len(parts) >= 3:
                            extracted = parts[1].strip()
                            json.loads(extracted)
                            return extracted
                    
                    start = response_text.find('{')
                    if start != -1:
                        end = response_text.rfind('}')
                        if end != -1:
                            extracted = response_text[start:end+1]
                            json.loads(extracted)
                            return extracted
                    
                    raise json.JSONDecodeError("Could not extract JSON", response_text, 0)
                    
            except Exception as e:
                is_overload = "overloaded_error" in str(e) or "529" in str(e)
                is_rate_limit = "rate_limit_error" in str(e) or "429" in str(e)
                
                if is_overload or is_rate_limit:
                    wait_time = min(base_delay * (2 ** attempt), 60)
                    if attempt < max_retries - 1:
                        logger.warning(f"API error. Waiting {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                elif attempt < 3:
                    wait_time = base_delay * (attempt + 1)
                    logger.warning(f"Error: {e}. Retrying...")
                    time.sleep(wait_time)
                    continue
                
                logger.error(f"LLM call failed: {e}")
                raise
        
        raise Exception(f"Failed after {max_retries} retries")
