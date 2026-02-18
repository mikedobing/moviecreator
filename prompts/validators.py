"""
Prompt validators for quality checking generated video prompts.

Validates prompt length, character consistency, temporal coherence,
and required fields before prompts enter the job queue.
"""

from typing import List, Dict, Set
from extraction.models import VideoPrompt, ValidationResult, ConsistencyReport, TemporalReport


class PromptValidator:
    """Quality checks on generated video prompts."""

    # Most video APIs accept ~500 tokens; rough estimate = 4 chars per token
    MAX_PROMPT_LENGTH = 2000  # characters (~500 tokens)
    MIN_PROMPT_LENGTH = 50   # Too short = low quality

    REQUIRED_FIELDS = ["prompt_text", "duration_seconds", "scene_id", "prompt_type"]

    @staticmethod
    def validate_prompt(prompt: VideoPrompt) -> ValidationResult:
        """Run all validation checks on a single prompt."""
        errors = []
        warnings = []

        # Required fields
        for field in PromptValidator.REQUIRED_FIELDS:
            val = getattr(prompt, field, None)
            if not val:
                errors.append(f"Missing required field: {field}")

        # Prompt length
        if len(prompt.prompt_text) > PromptValidator.MAX_PROMPT_LENGTH:
            warnings.append(
                f"Prompt length ({len(prompt.prompt_text)} chars) exceeds "
                f"recommended max ({PromptValidator.MAX_PROMPT_LENGTH}). "
                f"May be truncated by API."
            )
        if len(prompt.prompt_text) < PromptValidator.MIN_PROMPT_LENGTH:
            errors.append(
                f"Prompt too short ({len(prompt.prompt_text)} chars). "
                f"Minimum {PromptValidator.MIN_PROMPT_LENGTH} chars for quality."
            )

        # Duration bounds
        if prompt.duration_seconds < 2:
            errors.append(f"Duration too short: {prompt.duration_seconds}s (min 2s)")
        if prompt.duration_seconds > 20:
            warnings.append(f"Duration {prompt.duration_seconds}s exceeds typical API max (15s)")

        # Aspect ratio
        valid_ratios = {"16:9", "9:16", "1:1"}
        if prompt.aspect_ratio not in valid_ratios:
            warnings.append(f"Non-standard aspect ratio: {prompt.aspect_ratio}")

        # Motion intensity
        valid_motion = {"low", "medium", "high"}
        if prompt.motion_intensity not in valid_motion:
            warnings.append(f"Unknown motion intensity: {prompt.motion_intensity}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def check_character_consistency(
        prompts: List[VideoPrompt],
        character_name: str,
    ) -> ConsistencyReport:
        """
        Check that the same character is described consistently across all prompts.

        Looks for the character's consistency tags and verifies they match
        across all clips featuring that character.
        """
        appearances = []
        descriptions_seen: Set[str] = set()

        for prompt in prompts:
            # Check if character appears in this prompt
            if character_name.lower() in prompt.prompt_text.lower():
                appearances.append(prompt.prompt_id)
                # Extract consistency tags for this character
                for tag in prompt.character_consistency_tags:
                    if character_name.lower() in tag.lower():
                        descriptions_seen.add(tag)

        discrepancies = []
        if len(descriptions_seen) > 1:
            discrepancies.append(
                f"Character '{character_name}' has {len(descriptions_seen)} "
                f"different descriptions across {len(appearances)} appearances"
            )

        return ConsistencyReport(
            character_name=character_name,
            total_appearances=len(appearances),
            consistent_descriptions=len(descriptions_seen) <= 1,
            discrepancies=discrepancies,
        )

    @staticmethod
    def check_temporal_coherence(
        prompts: List[VideoPrompt],
    ) -> TemporalReport:
        """
        Check that time of day flows logically across sequential clips within a scene.

        Validates that clips within the same scene don't have contradictory
        temporal markers.
        """
        issues = []

        # Group prompts by scene
        scene_prompts: Dict[str, List[VideoPrompt]] = {}
        for prompt in prompts:
            scene_prompts.setdefault(prompt.scene_id, []).append(prompt)

        time_indicators = {
            "dawn": 0, "morning": 1, "day": 2, "afternoon": 3,
            "dusk": 4, "evening": 5, "night": 6,
        }

        for scene_id, scene_clips in scene_prompts.items():
            sorted_clips = sorted(scene_clips, key=lambda p: p.clip_index)
            times_found = []
            for clip in sorted_clips:
                text_lower = clip.prompt_text.lower()
                for time_word, order in time_indicators.items():
                    if time_word in text_lower:
                        times_found.append((clip.clip_index, time_word, order))
                        break

            # Check for temporal regression within a scene
            if len(times_found) >= 2:
                for i in range(1, len(times_found)):
                    prev_clip, prev_time, prev_order = times_found[i - 1]
                    curr_clip, curr_time, curr_order = times_found[i]
                    if curr_order < prev_order:
                        issues.append(
                            f"Scene {scene_id}: time goes backwards from "
                            f"'{prev_time}' (clip {prev_clip}) to "
                            f"'{curr_time}' (clip {curr_clip})"
                        )

        return TemporalReport(
            is_coherent=len(issues) == 0,
            issues=issues,
        )

    @staticmethod
    def validate_all(prompts: List[VideoPrompt]) -> Dict:
        """Run all validations on a full set of prompts."""
        # Individual prompt validation
        results = []
        total_errors = 0
        total_warnings = 0
        for prompt in prompts:
            result = PromptValidator.validate_prompt(prompt)
            results.append(result)
            total_errors += len(result.errors)
            total_warnings += len(result.warnings)

        # Character consistency
        all_chars: Set[str] = set()
        for prompt in prompts:
            for tag in prompt.character_consistency_tags:
                char_name = tag.split(":")[0].strip()
                all_chars.add(char_name)

        consistency_reports = []
        for char in all_chars:
            report = PromptValidator.check_character_consistency(prompts, char)
            consistency_reports.append(report)

        # Temporal coherence
        temporal_report = PromptValidator.check_temporal_coherence(prompts)

        return {
            "total_prompts": len(prompts),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "all_valid": total_errors == 0,
            "consistency_reports": consistency_reports,
            "temporal_report": temporal_report,
        }
