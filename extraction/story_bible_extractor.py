"""Story Bible extraction using LLM."""
import json
import time
from typing import List, Dict, Any
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from utils.logger import setup_logger
from extraction.models import (
    StoryBible,
    CharacterProfile,
    Location,
    TimelinePeriod,
    NarrativeTone,
    PlotSummary
)
from extraction import prompts
from ingestion.models import NarrativeChunk
import config

logger = setup_logger(__name__)


class ExtractionError(Exception):
    """Raised when extraction fails."""
    pass


class StoryBibleExtractor:
    """Extracts Story Bible from narrative chunks using LLM."""
    
    def __init__(
        self,
        anthropic_client: Anthropic,
        model: str = config.ANTHROPIC_MODEL
    ):
        """Initialize extractor.
        
        Args:
            anthropic_client: Anthropic API client
            model: Model name to use
        """
        self.client = anthropic_client
        self.model = model
        self.total_tokens_used = 0
        
        logger.info(f"StoryBibleExtractor initialized with model: {model}")
    
    def extract(self, chunks: List[NarrativeChunk], novel_title: str, novel_id: str = None, use_checkpoints: bool = True) -> StoryBible:
        """Extract complete Story Bible from chunks.
        
        Args:
            chunks: List of narrative chunks
            novel_title: Novel title
            novel_id: Novel ID for checkpointing
            use_checkpoints: Whether to use checkpointing
            
        Returns:
            Complete StoryBible
        """
        from extraction.checkpoint import ExtractionCheckpoint
        
        logger.info(f"Starting Story Bible extraction for: {novel_title}")
        logger.info(f"Processing {len(chunks)} chunks")
        
        # Initialize checkpoint if novel_id provided
        checkpoint = None
        checkpoint_data = None
        if use_checkpoints and novel_id:
            checkpoint = ExtractionCheckpoint(novel_id)
            checkpoint_data = checkpoint.load()
            
            if checkpoint_data:
                logger.info(f"📁 Found checkpoint at stage: {checkpoint_data.get('stage', 'unknown')}")
        
        # Process in batches using map-reduce approach
        batch_size = config.BATCH_SIZE
        
        # Extract characters
        if checkpoint_data and 'characters' in checkpoint_data:
            logger.info("✓ Loading characters from checkpoint...")
            characters = [CharacterProfile(**c) for c in checkpoint_data['characters']]
        else:
            logger.info("Extracting characters...")
            characters = self._extract_characters(chunks, batch_size)
            
            # Save checkpoint
            if checkpoint:
                checkpoint.save({
                    'stage': 'characters_complete',
                    'characters': [c.model_dump() for c in characters],
                    'tokens_used': self.total_tokens_used
                })
        
        # Extract locations
        if checkpoint_data and 'locations' in checkpoint_data:
            logger.info("✓ Loading locations from checkpoint...")
            locations = [Location(**loc) for loc in checkpoint_data['locations']]
        else:
            logger.info("Extracting locations...")
            locations = self._extract_locations(chunks, batch_size)
            
            # Save checkpoint
            if checkpoint:
                checkpoint_data = checkpoint.load() or {}
                checkpoint_data.update({
                    'stage': 'locations_complete',
                    'locations': [loc.model_dump() for loc in locations],
                    'tokens_used': self.total_tokens_used
                })
                checkpoint.save(checkpoint_data)
        
        # Extract tone (use sample chunks - first, middle, last)
        sample_chunks = self._get_sample_chunks(chunks, n=10)
        
        if checkpoint_data and 'tone' in checkpoint_data:
            logger.info("✓ Loading tone from checkpoint...")
            tone = NarrativeTone(**checkpoint_data['tone'])
        else:
            logger.info("Extracting narrative tone...")
            tone = self._extract_tone(sample_chunks)
            
            # Save checkpoint
            if checkpoint:
                checkpoint_data = checkpoint.load() or {}
                checkpoint_data.update({
                    'stage': 'tone_complete',
                    'tone': tone.model_dump(),
                    'tokens_used': self.total_tokens_used
                })
                checkpoint.save(checkpoint_data)
        
        # Extract plot
        if checkpoint_data and 'plot' in checkpoint_data:
            logger.info("✓ Loading plot from checkpoint...")
            plot = PlotSummary(**checkpoint_data['plot'])
        else:
            logger.info("Extracting plot summary...")
            plot = self._extract_plot(sample_chunks)
            
            # Save checkpoint
            if checkpoint:
                checkpoint_data = checkpoint.load() or {}
                checkpoint_data.update({
                    'stage': 'plot_complete',
                    'plot': plot.model_dump(),
                    'tokens_used': self.total_tokens_used
                })
                checkpoint.save(checkpoint_data)
        
        # Extract world rules
        if checkpoint_data and 'world_rules' in checkpoint_data:
            logger.info("✓ Loading world rules from checkpoint...")
            world_rules = checkpoint_data['world_rules']
        else:
            logger.info("Extracting world rules...")
            world_rules = self._extract_world_rules(sample_chunks)
            
            # Save checkpoint
            if checkpoint:
                checkpoint_data = checkpoint.load() or {}
                checkpoint_data.update({
                    'stage': 'world_rules_complete',
                    'world_rules': world_rules,
                    'tokens_used': self.total_tokens_used
                })
                checkpoint.save(checkpoint_data)
        
        # Extract timeline from sample
        if checkpoint_data and 'timeline' in checkpoint_data:
            logger.info("✓ Loading timeline from checkpoint...")
            timeline = TimelinePeriod(**checkpoint_data['timeline'])
        else:
            logger.info("Extracting timeline...")
            timeline = self._extract_timeline(sample_chunks)
            
            # Save checkpoint
            if checkpoint:
                checkpoint_data = checkpoint.load() or {}
                checkpoint_data.update({
                    'stage': 'timeline_complete',
                    'timeline': timeline.model_dump(),
                    'tokens_used': self.total_tokens_used
                })
                checkpoint.save(checkpoint_data)
        
        # Generate visual style notes
        visual_style_notes = self._generate_visual_style_notes(tone, locations)
        
        story_bible = StoryBible(
            novel_title=novel_title,
            characters=characters,
            locations=locations,
            timeline=timeline,
            tone=tone,
            plot=plot,
            world_rules=world_rules,
            visual_style_notes=visual_style_notes
        )
        
        # Clear checkpoint on success
        if checkpoint:
            checkpoint.clear()
        
        logger.info(f"Story Bible extraction complete. Total tokens used: {self.total_tokens_used}")
        logger.info(f"Extracted: {len(characters)} characters, {len(locations)} locations")
        
        return story_bible
    
    def _get_sample_chunks(self, chunks: List[NarrativeChunk], n: int = 10) -> List[NarrativeChunk]:
        """Get representative sample of chunks.
        
        Args:
            chunks: All chunks
            n: Number of samples
            
        Returns:
            Sample chunks from beginning, middle, and end
        """
        if len(chunks) <= n:
            return chunks
        
        # Get chunks from beginning, middle, and end
        step = len(chunks) // n
        return [chunks[i * step] for i in range(n)]
    
    def _extract_characters(
        self,
        chunks: List[NarrativeChunk],
        batch_size: int
    ) -> List[CharacterProfile]:
        """Extract character profiles using map-reduce.
        
        Args:
            chunks: Narrative chunks
            batch_size: Chunks per batch
            
        Returns:
            List of unique character profiles
        """
        all_profiles = []
        
        # Process in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            chunk_texts = [chunk.text for chunk in batch]
            
            prompt = prompts.character_extraction_prompt(chunk_texts)
            result = self._call_llm(prompt, expect_json=True)
            
            try:
                profiles_data = json.loads(result)
                for profile_dict in profiles_data:
                    all_profiles.append(CharacterProfile(**profile_dict))
            except Exception as e:
                logger.warning(f"Failed to parse character profiles from batch {i}: {e}")
            
            time.sleep(config.API_CALL_DELAY)
        
        # Merge duplicates
        if len(all_profiles) > 0:
            all_profiles = self._merge_duplicate_characters(all_profiles)
        
        return all_profiles
    
    def _extract_locations(
        self,
        chunks: List[NarrativeChunk],
        batch_size: int
    ) -> List[Location]:
        """Extract locations using map-reduce.
        
        Args:
            chunks: Narrative chunks
            batch_size: Chunks per batch
            
        Returns:
            List of locations
        """
        all_locations = []
        location_names_seen = set()
        
        # Process in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            chunk_texts = [chunk.text for chunk in batch]
            
            prompt = prompts.location_extraction_prompt(chunk_texts)
            result = self._call_llm(prompt, expect_json=True)
            
            try:
                locations_data = json.loads(result)
                for loc_dict in locations_data:
                    # Simple deduplication by name
                    if loc_dict['name'] not in location_names_seen:
                        all_locations.append(Location(**loc_dict))
                        location_names_seen.add(loc_dict['name'])
            except Exception as e:
                logger.warning(f"Failed to parse locations from batch {i}: {e}")
            
            time.sleep(config.API_CALL_DELAY)
        
        return all_locations
    
    def _extract_tone(self, chunks: List[NarrativeChunk]) -> NarrativeTone:
        """Extract narrative tone.
        
        Args:
            chunks: Sample chunks
            
        Returns:
            NarrativeTone
        """
        chunk_texts = [chunk.text for chunk in chunks]
        prompt = prompts.tone_extraction_prompt(chunk_texts)
        result = self._call_llm(prompt, expect_json=True)
        
        try:
            tone_data = json.loads(result)
            return NarrativeTone(**tone_data)
        except Exception as e:
            logger.error(f"Failed to parse tone: {e}")
            # Return default
            return NarrativeTone(
                genre=["unknown"],
                mood="neutral",
                pacing="moderate",
                style_notes="",
                violence_level="unknown",
                content_warnings=[]
            )
    
    def _extract_plot(self, chunks: List[NarrativeChunk]) -> PlotSummary:
        """Extract plot summary.
        
        Args:
            chunks: Sample chunks
            
        Returns:
            PlotSummary
        """
        chunk_texts = [chunk.text for chunk in chunks]
        prompt = prompts.plot_summary_prompt(chunk_texts)
        result = self._call_llm(prompt, expect_json=True)
        
        try:
            plot_data = json.loads(result)
            return PlotSummary(**plot_data)
        except Exception as e:
            logger.error(f"Failed to parse plot: {e}")
            return PlotSummary(
                logline="",
                synopsis="",
                acts=[],
                key_themes=[]
            )
    
    def _extract_world_rules(self, chunks: List[NarrativeChunk]) -> List[str]:
        """Extract world-building rules.
        
        Args:
            chunks: Sample chunks
            
        Returns:
            List of world rules
        """
        chunk_texts = [chunk.text for chunk in chunks]
        prompt = prompts.world_rules_prompt(chunk_texts)
        result = self._call_llm(prompt, expect_json=True)
        
        try:
            return json.loads(result)
        except Exception as e:
            logger.warning(f"Failed to parse world rules: {e}")
            return []
    
    def _extract_timeline(self, chunks: List[NarrativeChunk]) -> TimelinePeriod:
        """Extract timeline/period information.
        
        Args:
            chunks: Sample chunks
            
        Returns:
            TimelinePeriod
        """
        # Simple timeline extraction
        chunk_texts = [chunk.text for chunk in chunks[:3]]
        text = "\n\n".join(chunk_texts)
        
        prompt = f"""Read this text and determine the time period/setting.

Return a JSON object with:
- description: Brief description (e.g. "Victorian England, 1887")
- era: Historical era
- technology_level: Available technology
- cultural_notes: Cultural context

TEXT:
{text}

Return ONLY valid JSON, no other text."""
        
        result = self._call_llm(prompt, expect_json=True)
        
        try:
            timeline_data = json.loads(result)
            return TimelinePeriod(**timeline_data)
        except Exception as e:
            logger.warning(f"Failed to parse timeline: {e}")
            return TimelinePeriod(
                description="Contemporary",
                era="Modern",
                technology_level="Current",
                cultural_notes=""
            )
    
    def _merge_duplicate_characters(
        self,
        profiles: List[CharacterProfile]
    ) -> List[CharacterProfile]:
        """Merge duplicate character profiles.
        
        Args:
            profiles: All character profiles
            
        Returns:
            Deduplicated profiles
        """
        if len(profiles) <= 5:
            return profiles
        
        logger.info(f"Merging {len(profiles)} character profiles...")
        
        profiles_dicts = [profile.model_dump() for profile in profiles]
        prompt = prompts.merge_character_profiles_prompt(profiles_dicts)
        result = self._call_llm(prompt, expect_json=True)
        
        try:
            merged_data = json.loads(result)
            merged_profiles = [CharacterProfile(**p) for p in merged_data]
            logger.info(f"Merged to {len(merged_profiles)} unique characters")
            return merged_profiles
        except Exception as e:
            logger.error(f"Failed to merge characters: {e}")
            return profiles
    
    def _generate_visual_style_notes(
        self,
        tone: NarrativeTone,
        locations: List[Location]
    ) -> str:
        """Generate overall visual style notes.
        
        Args:
            tone: Narrative tone
            locations: List of locations
            
        Returns:
            Visual style notes
        """
        return f"""Visual Style Guide:
- Genre: {', '.join(tone.genre)}
- Mood: {tone.mood}
- Style: {tone.style_notes}
- Primary locations: {', '.join([loc.name for loc in locations[:5]])}
- Violence level: {tone.violence_level}

Use these notes to maintain visual consistency across all generated video prompts."""
    
    def _call_llm(self, prompt: str, expect_json: bool = True) -> str:
        """Call Anthropic API with retry logic.
        
        Args:
            prompt: Prompt text
            expect_json: Whether to expect JSON response
            
        Returns:
            Response text
            
        Raises:
            ExtractionError: If call fails after retries
        """
        max_retries = 10  # More retries for overload errors
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=config.LLM_TEMPERATURE,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Track token usage
                self.total_tokens_used += message.usage.input_tokens + message.usage.output_tokens
                
                response_text = message.content[0].text
                
                # If expecting JSON, try to validate and extract it
                if expect_json:
                    # First, try to parse as-is
                    try:
                        json.loads(response_text)
                        return response_text
                    except json.JSONDecodeError:
                        # Try to extract JSON from markdown code blocks
                        extracted = None
                        
                        # Try ```json ... ```
                        if "```json" in response_text:
                            parts = response_text.split("```json")
                            if len(parts) > 1:
                                extracted = parts[1].split("```")[0].strip()
                        # Try ``` ... ``` (generic code block)
                        elif "```" in response_text:
                            parts = response_text.split("```")
                            if len(parts) >= 3:
                                extracted = parts[1].strip()
                        
                        # If we extracted something, try to parse it
                        if extracted:
                            try:
                                json.loads(extracted)
                                return extracted
                            except json.JSONDecodeError:
                                pass
                        
                        # Last resort: look for JSON array or object patterns
                        # Try to find first [ or { and last ] or }
                        start_arr = response_text.find('[')
                        start_obj = response_text.find('{')
                        
                        if start_arr != -1 or start_obj != -1:
                            # Use whichever comes first
                            if start_arr == -1:
                                start = start_obj
                                end_char = '}'
                            elif start_obj == -1:
                                start = start_arr
                                end_char = ']'
                            else:
                                start = min(start_arr, start_obj)
                                end_char = ']' if start == start_arr else '}'
                            
                            end = response_text.rfind(end_char)
                            if end != -1:
                                extracted = response_text[start:end+1]
                                try:
                                    json.loads(extracted)
                                    return extracted
                                except json.JSONDecodeError:
                                    pass
                        
                        # If we still can't parse, log the actual response and raise
                        logger.error(f"Could not extract valid JSON from response. First 500 chars: {response_text[:500]}")
                        raise json.JSONDecodeError("Could not parse or extract JSON", response_text, 0)
                
                return response_text
                
            except Exception as e:
                # Check if it's an overload error
                is_overload = "overloaded_error" in str(e) or "529" in str(e)
                is_rate_limit = "rate_limit_error" in str(e) or "429" in str(e)
                
                if is_overload or is_rate_limit:
                    # Exponential backoff for overload/rate limit errors
                    wait_time = min(base_delay * (2 ** attempt), 60)  # Cap at 60s
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"{'Overload' if is_overload else 'Rate limit'} error. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Failed after {max_retries} retries due to {'overload' if is_overload else 'rate limit'}")
                        raise ExtractionError(f"LLM call failed after {max_retries} retries: {e}")
                else:
                    # For other errors, retry with shorter wait
                    if attempt < 3:  # Only 3 retries for non-overload errors
                        wait_time = base_delay * (attempt + 1)
                        logger.warning(f"API error: {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"LLM call failed: {e}")
                        raise ExtractionError(f"LLM call failed: {e}")
        
        raise ExtractionError(f"LLM call failed after {max_retries} retries")

