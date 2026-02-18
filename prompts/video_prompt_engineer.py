"""
Video Prompt Engineer — Core logic for generating video prompts from scene breakdowns.

Takes SceneBreakdown objects (Phase 2 output) and engineers high-quality,
self-contained prompts for video generation APIs.
"""

import uuid
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime

from extraction.models import (
    SceneBreakdown, ShotSpec, VideoPrompt,
    VisualComposition, CharacterProfile
)
from prompts.templates import PromptTemplates
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VideoPromptEngineer:
    """Generates video prompts from scene breakdowns using template library."""

    # Duration defaults by shot type (seconds)
    DURATION_MAP = {
        "establishing": 7,
        "character_intro": 8,
        "dialogue_two_shot": 10,
        "dialogue_over_shoulder": 8,
        "action": 6,
        "reaction": 4,
        "transition": 5,
        "insert": 4,
        "montage": 6,
    }

    # Motion intensity by shot type
    MOTION_MAP = {
        "establishing": "low",
        "character_intro": "low",
        "dialogue_two_shot": "low",
        "dialogue_over_shoulder": "low",
        "action": "high",
        "reaction": "low",
        "transition": "medium",
        "insert": "low",
        "montage": "medium",
    }

    # Camera movement defaults by shot type
    CAMERA_MAP = {
        "establishing": "slow pan",
        "character_intro": "slow push-in",
        "dialogue_two_shot": "static",
        "dialogue_over_shoulder": "static",
        "action": "handheld tracking",
        "reaction": "very slow push-in",
        "transition": "dolly",
        "insert": "static",
        "montage": "tracking",
    }

    def __init__(self, story_bible: Dict[str, Any]):
        """
        Args:
            story_bible: Story Bible dict (Phase 1 output)
        """
        self.story_bible = story_bible
        self.templates = PromptTemplates()
        self._character_cache: Dict[str, Dict] = {}
        self._build_character_cache()

    def _build_character_cache(self):
        """Index characters by name and aliases for fast lookup."""
        characters = self.story_bible.get("characters", [])
        for char in characters:
            name = char.get("name", "")
            self._character_cache[name.lower()] = char
            for alias in char.get("aliases", []):
                self._character_cache[alias.lower()] = char

    def generate_prompts_for_scene(
        self,
        scene_breakdown: Dict[str, Any],
        novel_id: str,
    ) -> List[VideoPrompt]:
        """
        Generate all video prompts for a single scene.

        Args:
            scene_breakdown: Scene breakdown dict from Phase 2
            novel_id: Novel UUID

        Returns:
            List of VideoPrompt objects for this scene
        """
        scene_id = scene_breakdown.get("scene_id", scene_breakdown.get("breakdown_id", ""))
        
        # Step 1: Determine shot sequence
        shot_specs = self._determine_shot_sequence(scene_breakdown)
        
        # Step 2: Build prompts from shot specs
        prompts = []
        for shot in shot_specs:
            prompt = self._build_prompt_from_shot_spec(
                shot_spec=shot,
                scene_breakdown=scene_breakdown,
                novel_id=novel_id,
                scene_id=scene_id,
            )
            prompts.append(prompt)
        
        return prompts

    def _determine_shot_sequence(
        self, scene_breakdown: Dict[str, Any]
    ) -> List[ShotSpec]:
        """
        Determine the sequence of shots/clips needed for a scene.

        Logic:
        1. Establishing shot (if scene has a location)
        2. Character introductions (for each character present)
        3. Dialogue coverage (if dialogue present)
        4. Action beats (based on composition key moments)
        5. Transition shot (if scene seems to end a sequence)
        """
        shots: List[ShotSpec] = []
        clip_index = 0
        
        characters_with_descs = scene_breakdown.get("characters_with_descriptions", {})
        character_names = list(characters_with_descs.keys())
        slug_line = scene_breakdown.get("slug_line", "")
        dialogue_present = scene_breakdown.get("dialogue_present", False)
        composition = scene_breakdown.get("composition", {})
        scene_type = scene_breakdown.get("scene_type", "")
        estimated_clips = scene_breakdown.get("estimated_clip_count", 3)

        # 1. Establishing shot — for scenes with a specified location
        if slug_line:
            shots.append(ShotSpec(
                shot_type="establishing",
                clip_index=clip_index,
                characters=[],
                camera_movement=self.CAMERA_MAP["establishing"],
                framing="wide",
                duration_seconds=self.DURATION_MAP["establishing"],
                description=f"Establishing: {slug_line}",
            ))
            clip_index += 1

        # 2. Character introductions — one per character, up to 2
        for char_name in character_names[:2]:
            shots.append(ShotSpec(
                shot_type="character_intro",
                clip_index=clip_index,
                characters=[char_name],
                camera_movement=self.CAMERA_MAP["character_intro"],
                framing="medium",
                duration_seconds=self.DURATION_MAP["character_intro"],
                description=f"Introduce {char_name}",
            ))
            clip_index += 1

        # 3. Dialogue coverage
        if dialogue_present and len(character_names) >= 2:
            # Two-shot
            shots.append(ShotSpec(
                shot_type="dialogue_two_shot",
                clip_index=clip_index,
                characters=character_names[:2],
                camera_movement="static",
                framing="medium",
                duration_seconds=self.DURATION_MAP["dialogue_two_shot"],
                description=f"Dialogue two-shot: {character_names[0]} and {character_names[1]}",
            ))
            clip_index += 1

            # Over-shoulder on each main character
            for char in character_names[:2]:
                others = [c for c in character_names[:2] if c != char]
                listener = others[0] if others else ""
                shots.append(ShotSpec(
                    shot_type="dialogue_over_shoulder",
                    clip_index=clip_index,
                    characters=[char, listener] if listener else [char],
                    camera_movement="static",
                    framing="close_up",
                    duration_seconds=self.DURATION_MAP["dialogue_over_shoulder"],
                    description=f"Over-shoulder on {char}",
                ))
                clip_index += 1

        elif dialogue_present and len(character_names) == 1:
            # Solo character speaking — use reaction/close-up instead
            shots.append(ShotSpec(
                shot_type="reaction",
                clip_index=clip_index,
                characters=[character_names[0]],
                camera_movement="very slow push-in",
                framing="close_up",
                duration_seconds=self.DURATION_MAP["reaction"],
                description=f"Close-up: {character_names[0]} speaking",
            ))
            clip_index += 1

        # 4. Action beats — based on key moment from composition
        key_moment = composition.get("key_moment_description", "")
        if key_moment:
            action_chars = character_names[:2] if character_names else []
            shots.append(ShotSpec(
                shot_type="action",
                clip_index=clip_index,
                characters=action_chars,
                camera_movement=self.CAMERA_MAP["action"],
                framing="medium",
                duration_seconds=self.DURATION_MAP["action"],
                description=f"Action: {key_moment[:80]}",
            ))
            clip_index += 1

        # 5. Reaction shot — for emotional scenes
        emotional_beat = scene_breakdown.get("emotional_beat", "")
        if emotional_beat and character_names and len(shots) < estimated_clips:
            main_char = character_names[0]
            shots.append(ShotSpec(
                shot_type="reaction",
                clip_index=clip_index,
                characters=[main_char],
                camera_movement="very slow push-in",
                framing="close_up",
                duration_seconds=self.DURATION_MAP["reaction"],
                description=f"Reaction: {main_char} — {emotional_beat[:60]}",
            ))
            clip_index += 1

        # 6. Insert shot — if props mentioned
        props = scene_breakdown.get("props_and_set_dressing", [])
        if props and len(shots) < estimated_clips:
            main_prop = props[0]
            shots.append(ShotSpec(
                shot_type="insert",
                clip_index=clip_index,
                characters=[],
                camera_movement="static",
                framing="extreme_close_up",
                duration_seconds=self.DURATION_MAP["insert"],
                description=f"Insert: {main_prop}",
            ))
            clip_index += 1

        # Ensure at least 2 shots per scene
        if len(shots) < 2 and character_names:
            shots.append(ShotSpec(
                shot_type="action",
                clip_index=clip_index,
                characters=character_names[:2],
                camera_movement="tracking",
                framing="medium",
                duration_seconds=6,
                description=f"Scene action: {emotional_beat[:60]}" if emotional_beat else "Scene action",
            ))

        return shots

    def _build_prompt_from_shot_spec(
        self,
        shot_spec: ShotSpec,
        scene_breakdown: Dict[str, Any],
        novel_id: str,
        scene_id: str,
    ) -> VideoPrompt:
        """Build a complete VideoPrompt from a ShotSpec and scene breakdown."""
        
        characters_with_descs = scene_breakdown.get("characters_with_descriptions", {})
        composition = scene_breakdown.get("composition", {})
        location_desc = scene_breakdown.get("location_visual_description", "")
        slug_line = scene_breakdown.get("slug_line", "")
        era = self.story_bible.get("timeline", {}).get("era", "")
        colour_palette = composition.get("colour_palette", "")
        lighting = composition.get("lighting", "")
        
        # Determine time of day and weather from slug line
        time_of_day = self._extract_time_of_day(slug_line)
        weather = self._extract_weather(scene_breakdown)
        atmosphere = scene_breakdown.get("emotional_beat", "")

        # Build the prompt text using templates
        prompt_text = self._generate_prompt_text(
            shot_spec=shot_spec,
            characters_with_descs=characters_with_descs,
            composition=composition,
            location_desc=location_desc,
            slug_line=slug_line,
            time_of_day=time_of_day,
            weather=weather,
            atmosphere=atmosphere,
            era=era,
            colour_palette=colour_palette,
            lighting=lighting,
        )

        # Build character consistency tags
        consistency_tags = []
        for char_name in shot_spec.characters:
            tags = self._extract_character_appearance_tags(char_name, characters_with_descs)
            consistency_tags.extend(tags)

        # Build negative and audio prompts
        negative_prompt = self.templates.build_negative_prompt(era=era)
        audio_prompt = self._build_audio_prompt(scene_breakdown)

        return VideoPrompt(
            prompt_id=str(uuid.uuid4()),
            scene_id=scene_id,
            novel_id=novel_id,
            clip_index=shot_spec.clip_index,
            prompt_type=shot_spec.shot_type,
            prompt_text=prompt_text,
            negative_prompt=negative_prompt,
            duration_seconds=shot_spec.duration_seconds,
            aspect_ratio="16:9",
            motion_intensity=self.MOTION_MAP.get(shot_spec.shot_type, "medium"),
            camera_movement=shot_spec.camera_movement,
            character_consistency_tags=consistency_tags,
            audio_prompt=audio_prompt,
            generation_params={
                "resolution": "1080p",
                "fps": 24,
            },
            estimated_cost_usd=self._estimate_clip_cost(shot_spec.duration_seconds),
        )

    def _generate_prompt_text(
        self,
        shot_spec: ShotSpec,
        characters_with_descs: Dict[str, str],
        composition: Dict[str, Any],
        location_desc: str,
        slug_line: str,
        time_of_day: str,
        weather: str,
        atmosphere: str,
        era: str,
        colour_palette: str,
        lighting: str,
    ) -> str:
        """Route to the appropriate template based on shot type."""

        char_names = shot_spec.characters
        char_descs = {name: self._get_short_description(name, characters_with_descs) for name in char_names}

        if shot_spec.shot_type == "establishing":
            return self.templates.establishing_shot(
                location=location_desc or slug_line,
                time_of_day=time_of_day,
                weather=weather,
                atmosphere=atmosphere,
                era=era,
                colour_palette=colour_palette,
                camera_movement=shot_spec.camera_movement,
            )

        elif shot_spec.shot_type == "character_intro":
            char = char_names[0] if char_names else "Unknown"
            desc = char_descs.get(char, "")
            key_moment = composition.get("key_moment_description", "stands in the scene")
            return self.templates.character_introduction(
                character_name=char,
                physical_description=desc,
                action=self._extract_character_action(char, key_moment),
                location_context=location_desc or slug_line,
                lighting=lighting,
                mood=atmosphere,
                camera_movement=shot_spec.camera_movement,
            )

        elif shot_spec.shot_type == "dialogue_two_shot":
            c1 = char_names[0] if len(char_names) > 0 else "Character A"
            c2 = char_names[1] if len(char_names) > 1 else "Character B"
            return self.templates.dialogue_two_shot(
                char1_name=c1,
                char1_desc=char_descs.get(c1, ""),
                char2_name=c2,
                char2_desc=char_descs.get(c2, ""),
                emotional_dynamic=atmosphere,
                setting_detail=location_desc or slug_line,
                lighting=lighting,
            )

        elif shot_spec.shot_type == "dialogue_over_shoulder":
            speaker = char_names[0] if len(char_names) > 0 else "Speaker"
            listener = char_names[1] if len(char_names) > 1 else "Listener"
            bg = composition.get("background", location_desc)
            return self.templates.dialogue_over_shoulder(
                speaking_char=speaker,
                speaking_char_desc=char_descs.get(speaker, ""),
                listening_char=listener,
                listening_char_desc=char_descs.get(listener, ""),
                emotional_beat=atmosphere,
                background=bg,
                camera_movement=shot_spec.camera_movement,
            )

        elif shot_spec.shot_type == "action":
            action_desc = composition.get("key_moment_description", shot_spec.description)
            chars_in_shot = ", ".join(
                f"{name} ({char_descs.get(name, '')})" for name in char_names
            ) if char_names else "scene elements"
            return self.templates.action_sequence(
                action_description=action_desc,
                characters_in_shot=chars_in_shot,
                environment=location_desc or slug_line,
                camera_movement=shot_spec.camera_movement,
                motion_intensity=self.MOTION_MAP.get(shot_spec.shot_type, "medium"),
                lighting=lighting,
            )

        elif shot_spec.shot_type == "reaction":
            char = char_names[0] if char_names else "Character"
            desc = char_descs.get(char, "")
            return self.templates.reaction_close_up(
                character_name=char,
                character_desc=desc,
                emotion=atmosphere,
                micro_expression=self._derive_micro_expression(atmosphere),
                lighting=lighting,
                camera_movement=shot_spec.camera_movement,
            )

        elif shot_spec.shot_type == "transition":
            fg = composition.get("foreground", "")
            bg = composition.get("background", "")
            return self.templates.transition_shot(
                from_element=fg,
                to_element=bg,
                transition_type="dissolve",
            )

        elif shot_spec.shot_type == "insert":
            props = shot_spec.description.replace("Insert: ", "")
            return self.templates.insert_shot(
                object_focus=props,
                significance="narrative detail",
                lighting=lighting,
            )

        elif shot_spec.shot_type == "montage":
            return self.templates.montage_clip(
                activity=shot_spec.description,
                setting=location_desc or slug_line,
                characters=", ".join(char_names) if char_names else "scene elements",
            )

        else:
            # Fallback: build a generic cinematic prompt
            return (
                f"{shot_spec.description}. "
                f"Setting: {location_desc or slug_line}. "
                f"Lighting: {lighting}. "
                f"{PromptTemplates.CINEMATIC_SUFFIX}"
            )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _get_short_description(
        self, char_name: str, characters_with_descs: Dict[str, str]
    ) -> str:
        """Get a concise character description (max 3 distinctive features)."""
        full_desc = characters_with_descs.get(char_name, "")
        if not full_desc:
            # Fall back to Story Bible
            char_data = self._character_cache.get(char_name.lower(), {})
            full_desc = char_data.get("physical_description", "")
        
        if len(full_desc) > 200:
            # Truncate to ~200 chars at a sentence boundary
            truncated = full_desc[:200]
            last_period = truncated.rfind(".")
            if last_period > 100:
                return truncated[:last_period + 1]
            return truncated + "..."
        return full_desc

    def _extract_character_appearance_tags(
        self, char_name: str, characters_with_descs: Dict[str, str]
    ) -> List[str]:
        """Extract 2-3 distinctive physical anchors for character consistency."""
        desc = characters_with_descs.get(char_name, "")
        if not desc:
            char_data = self._character_cache.get(char_name.lower(), {})
            desc = char_data.get("physical_description", "")
        
        # Return the character name + key description as consistency tag
        if desc:
            return [f"{char_name}: {desc[:150]}"]
        return [char_name]

    def _extract_time_of_day(self, slug_line: str) -> str:
        """Extract time of day from slug line."""
        slug_upper = slug_line.upper()
        for tod in ["DAWN", "MORNING", "DAY", "AFTERNOON", "DUSK", "EVENING", "NIGHT", "CONTINUOUS"]:
            if tod in slug_upper:
                return tod.lower()
        return "day"

    def _extract_weather(self, scene_breakdown: Dict[str, Any]) -> str:
        """Derive weather from scene breakdown hints."""
        ambient = scene_breakdown.get("ambient_sound", "").lower()
        composition = scene_breakdown.get("composition", {})
        bg = composition.get("background", "").lower()
        
        if "rain" in ambient or "rain" in bg:
            return "rainy"
        if "storm" in ambient or "thunder" in bg:
            return "stormy"
        if "wind" in ambient:
            return "windy"
        if "snow" in bg:
            return "snowy"
        return "clear"

    def _extract_character_action(self, char_name: str, key_moment: str) -> str:
        """Extract or derive a character's action from the key moment."""
        # If the key moment mentions the character, extract context
        if char_name.lower() in key_moment.lower():
            return key_moment[:120]
        return f"appears in the scene, {key_moment[:80]}"

    def _derive_micro_expression(self, emotional_beat: str) -> str:
        """Derive a micro-expression hint from the emotional beat."""
        beat_lower = emotional_beat.lower()
        if any(w in beat_lower for w in ["fear", "terror", "horror", "dread"]):
            return "widened eyes, tightened jaw, slight tremor"
        if any(w in beat_lower for w in ["anger", "rage", "fury"]):
            return "clenched jaw, narrowed eyes, flared nostrils"
        if any(w in beat_lower for w in ["sad", "grief", "loss", "sorrow"]):
            return "glistening eyes, quivering lower lip, downcast gaze"
        if any(w in beat_lower for w in ["joy", "happy", "relief", "hope"]):
            return "slight smile, brightened eyes, relaxed brow"
        if any(w in beat_lower for w in ["shock", "surprise", "discover"]):
            return "raised eyebrows, parted lips, widened eyes"
        if any(w in beat_lower for w in ["tension", "suspense", "wary"]):
            return "tight lips, alert eyes, subtle frown"
        if any(w in beat_lower for w in ["determination", "resolve"]):
            return "set jaw, focused gaze, squared shoulders"
        return "subtle shift in expression, internal processing"

    def _build_audio_prompt(self, scene_breakdown: Dict[str, Any]) -> str:
        """Build an audio generation prompt from scene breakdown hints."""
        parts = []
        ambient = scene_breakdown.get("ambient_sound", "")
        if ambient:
            parts.append(f"Ambient: {ambient}")
        music = scene_breakdown.get("music_mood", "")
        if music:
            parts.append(f"Music: {music}")
        if scene_breakdown.get("dialogue_present"):
            parts.append("Dialogue present (requires separate TTS)")
        return ". ".join(parts) if parts else ""

    def _estimate_clip_cost(self, duration_seconds: int, resolution: str = "1080p") -> float:
        """Estimate cost for a single clip."""
        # Seedance 2.0 approximate pricing
        cost_per_minute = {
            "720p": 0.10,
            "1080p": 0.30,
            "2k": 0.80,
        }
        rate = cost_per_minute.get(resolution, 0.30)
        return round((duration_seconds / 60.0) * rate, 4)

    def generate_prompts_for_all_scenes(
        self,
        breakdowns: List[Dict[str, Any]],
        novel_id: str,
    ) -> List[VideoPrompt]:
        """Generate prompts for all scene breakdowns."""
        all_prompts = []
        for breakdown in breakdowns:
            scene_prompts = self.generate_prompts_for_scene(breakdown, novel_id)
            all_prompts.extend(scene_prompts)
            logger.info(
                f"Scene {breakdown.get('scene_number', '?')}: "
                f"generated {len(scene_prompts)} prompts"
            )
        return all_prompts
