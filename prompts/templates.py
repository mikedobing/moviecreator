"""
Prompt templates for video generation.

Each template produces a detailed, self-contained video prompt that works
even if copy-pasted into a web UI with zero additional context.

Template philosophy:
  1. WHAT — subject/action
  2. WHERE — setting/environment
  3. HOW — camera, lighting, mood
  4. STYLE — cinematic references, technical specs
"""

from typing import List, Optional


class PromptTemplates:
    """Library of shot-type templates for video generation prompts."""

    # ------------------------------------------------------------------
    # Style suffixes (appended to all prompts for consistent look)
    # ------------------------------------------------------------------
    CINEMATIC_SUFFIX = (
        "Cinematic quality, photorealistic, "
        "shot on 35mm film, shallow depth of field, "
        "anamorphic lens, natural film grain."
    )

    # ------------------------------------------------------------------
    # Shot-type templates
    # ------------------------------------------------------------------

    @staticmethod
    def establishing_shot(
        location: str,
        time_of_day: str,
        weather: str,
        atmosphere: str,
        era: str,
        colour_palette: str = "",
        camera_movement: str = "slow pan",
    ) -> str:
        """Wide shot establishing a location — typically the first clip in a new scene."""
        parts = [
            f"Wide establishing shot of {location}.",
            f"{time_of_day}, {weather}.",
            f"Atmosphere: {atmosphere}.",
        ]
        if era and era.lower() not in ("modern", "contemporary", "present"):
            parts.append(f"Era: {era}.")
        if colour_palette:
            parts.append(f"Colour palette: {colour_palette}.")
        parts.append(f"Camera: {camera_movement}.")
        parts.append(PromptTemplates.CINEMATIC_SUFFIX)
        return " ".join(parts)

    @staticmethod
    def character_introduction(
        character_name: str,
        physical_description: str,
        action: str,
        location_context: str,
        lighting: str,
        mood: str,
        camera_movement: str = "slow push-in",
    ) -> str:
        """First appearance of a character in a scene."""
        parts = [
            f"Medium shot of {character_name} ({physical_description}).",
            f"{character_name} {action}.",
            f"Setting: {location_context}.",
            f"Lighting: {lighting}.",
            f"Mood: {mood}.",
            f"Camera: {camera_movement}.",
            PromptTemplates.CINEMATIC_SUFFIX,
        ]
        return " ".join(parts)

    @staticmethod
    def dialogue_two_shot(
        char1_name: str,
        char1_desc: str,
        char2_name: str,
        char2_desc: str,
        emotional_dynamic: str,
        setting_detail: str,
        lighting: str,
        action_hint: str = "",
    ) -> str:
        """Two characters in frame during a dialogue exchange."""
        parts = [
            f"Medium two-shot of {char1_name} ({char1_desc}) and {char2_name} ({char2_desc}).",
            f"They face each other, {emotional_dynamic}.",
        ]
        if action_hint:
            parts.append(f"{action_hint}.")
        parts.extend([
            f"Setting: {setting_detail}.",
            f"Lighting: {lighting}.",
            "Camera: static or gentle drift.",
            PromptTemplates.CINEMATIC_SUFFIX,
        ])
        return " ".join(parts)

    @staticmethod
    def dialogue_over_shoulder(
        speaking_char: str,
        speaking_char_desc: str,
        listening_char: str,
        listening_char_desc: str,
        emotional_beat: str,
        background: str,
        camera_movement: str = "static",
    ) -> str:
        """Over-the-shoulder shot during dialogue. Focus on the speaker's face."""
        parts = [
            f"Over-the-shoulder shot from behind {listening_char} ({listening_char_desc}),",
            f"looking at {speaking_char} ({speaking_char_desc}) speaking.",
            f"Emotional beat: {emotional_beat}.",
            f"Background: {background}.",
            f"Camera: {camera_movement}.",
            "Shallow depth of field, speaker sharp, listener softly blurred.",
            PromptTemplates.CINEMATIC_SUFFIX,
        ]
        return " ".join(parts)

    @staticmethod
    def action_sequence(
        action_description: str,
        characters_in_shot: str,
        environment: str,
        camera_movement: str = "handheld tracking",
        motion_intensity: str = "high",
        lighting: str = "",
        sound_design_hint: str = "",
    ) -> str:
        """Dynamic action — movement, chase, fight, physical activity."""
        parts = [
            f"{action_description}.",
            f"Characters: {characters_in_shot}.",
            f"Environment: {environment}.",
            f"Camera: {camera_movement}, {motion_intensity} motion intensity.",
        ]
        if lighting:
            parts.append(f"Lighting: {lighting}.")
        if sound_design_hint:
            parts.append(f"Sound design: {sound_design_hint}.")
        parts.append(PromptTemplates.CINEMATIC_SUFFIX)
        return " ".join(parts)

    @staticmethod
    def reaction_close_up(
        character_name: str,
        character_desc: str,
        emotion: str,
        micro_expression: str,
        lighting: str,
        camera_movement: str = "very slow push-in",
    ) -> str:
        """Close-up on character's face capturing emotional response."""
        parts = [
            f"Tight close-up on {character_name}'s face ({character_desc}).",
            f"Expression: {emotion} — {micro_expression}.",
            f"Lighting: {lighting}.",
            f"Camera: {camera_movement}.",
            "Extreme shallow depth of field, only the eyes in sharp focus.",
            PromptTemplates.CINEMATIC_SUFFIX,
        ]
        return " ".join(parts)

    @staticmethod
    def transition_shot(
        from_element: str,
        to_element: str,
        transition_type: str = "dissolve",
        time_passage: str = "none",
        visual_bridge: str = "",
    ) -> str:
        """Visual bridge between scenes or locations."""
        parts = [f"Transition shot: {transition_type}."]
        if time_passage != "none":
            parts.append(f"Time passage: {time_passage}.")
        if visual_bridge:
            parts.append(f"{visual_bridge}.")
        else:
            parts.append(f"From {from_element} to {to_element}.")
        parts.append("Smooth, atmospheric. " + PromptTemplates.CINEMATIC_SUFFIX)
        return " ".join(parts)

    @staticmethod
    def montage_clip(
        activity: str,
        setting: str,
        characters: str,
        progression_note: str = "",
        music_sync_hint: str = "",
    ) -> str:
        """Single clip in a montage sequence."""
        parts = [
            f"{activity}.",
            f"Characters: {characters}.",
            f"Setting: {setting}.",
        ]
        if progression_note:
            parts.append(f"Progression: {progression_note}.")
        if music_sync_hint:
            parts.append(f"Music sync: {music_sync_hint}.")
        parts.append(PromptTemplates.CINEMATIC_SUFFIX)
        return " ".join(parts)

    @staticmethod
    def insert_shot(
        object_focus: str,
        significance: str,
        framing: str = "extreme close-up",
        lighting: str = "",
        camera_movement: str = "static",
    ) -> str:
        """Detail shot of an object or prop with narrative importance."""
        parts = [
            f"{framing} of {object_focus}.",
            f"Narrative significance: {significance}.",
        ]
        if lighting:
            parts.append(f"Lighting: {lighting}.")
        parts.extend([
            f"Camera: {camera_movement}.",
            "Macro lens feel, razor-thin depth of field.",
            PromptTemplates.CINEMATIC_SUFFIX,
        ])
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Negative prompt builder
    # ------------------------------------------------------------------

    @staticmethod
    def build_negative_prompt(
        era: str = "",
        extra_exclusions: Optional[List[str]] = None,
    ) -> str:
        """Build a negative prompt to exclude common video-gen artifacts."""
        exclusions = [
            "blurry", "low resolution", "pixelated",
            "text overlays", "logos", "watermarks",
            "face distortion", "hand deformities", "morphing artifacts",
            "duplicate characters in frame",
            "unrealistic physics",
            "anime style", "cartoon style",
        ]
        # Era-specific exclusions
        if era and era.lower() not in ("modern", "contemporary", "present", ""):
            exclusions.extend([
                "modern vehicles", "smartphones", "electric lights (unless period-appropriate)",
                "contemporary clothing",
            ])
        if extra_exclusions:
            exclusions.extend(extra_exclusions)
        return ", ".join(exclusions)
