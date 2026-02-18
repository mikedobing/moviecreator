"""
API adapters for video generation providers.

Abstract layer so prompts can be re-targeted to different video APIs.
Phase 3 does NOT call these APIs — it only uses adapters for formatting,
cost estimation, and parameter validation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from extraction.models import VideoPrompt


class VideoAPIAdapter(ABC):
    """Abstract base class for video generation API adapters."""

    @abstractmethod
    def format_prompt(self, prompt: VideoPrompt) -> Dict[str, Any]:
        """Convert VideoPrompt to provider-specific API request format."""
        pass

    @abstractmethod
    def estimate_cost(self, prompt: VideoPrompt) -> float:
        """Estimate generation cost in USD."""
        pass

    @abstractmethod
    def get_max_duration(self) -> int:
        """Max clip length in seconds for this provider."""
        pass

    @abstractmethod
    def supports_audio_generation(self) -> bool:
        """Whether provider generates audio natively."""
        pass

    @abstractmethod
    def supports_reference_images(self) -> bool:
        """Whether provider accepts reference images for consistency."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider identifier string."""
        pass


class SeedanceAdapter(VideoAPIAdapter):
    """Adapter for Seedance 2.0 API (ByteDance)."""

    COST_PER_MINUTE = {
        "720p": 0.10,
        "1080p": 0.30,
        "2k": 0.80,
    }

    def format_prompt(self, prompt: VideoPrompt) -> Dict[str, Any]:
        resolution = prompt.generation_params.get("resolution", "1080p")
        return {
            "prompt": prompt.prompt_text,
            "negative_prompt": prompt.negative_prompt,
            "duration": prompt.duration_seconds,
            "aspect_ratio": prompt.aspect_ratio,
            "resolution": resolution,
            "motion_intensity": prompt.motion_intensity,
            "camera_movement": prompt.camera_movement,
            "audio_prompt": prompt.audio_prompt if prompt.audio_prompt else None,
            "reference_image": prompt.reference_image_path,
            "seed": None,  # Let API choose
        }

    def estimate_cost(self, prompt: VideoPrompt) -> float:
        resolution = prompt.generation_params.get("resolution", "1080p")
        rate = self.COST_PER_MINUTE.get(resolution, 0.30)
        return round((prompt.duration_seconds / 60.0) * rate, 4)

    def get_max_duration(self) -> int:
        return 15

    def supports_audio_generation(self) -> bool:
        return True

    def supports_reference_images(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "seedance"


class KlingAdapter(VideoAPIAdapter):
    """Adapter for Kling API (Kuaishou)."""

    COST_PER_MINUTE = {
        "720p": 0.15,
        "1080p": 0.40,
    }

    def format_prompt(self, prompt: VideoPrompt) -> Dict[str, Any]:
        return {
            "prompt": prompt.prompt_text,
            "negative_prompt": prompt.negative_prompt,
            "duration": min(prompt.duration_seconds, 10),  # Kling max ~10s
            "aspect_ratio": prompt.aspect_ratio,
            "mode": "standard",
            "reference_image": prompt.reference_image_path,
        }

    def estimate_cost(self, prompt: VideoPrompt) -> float:
        resolution = prompt.generation_params.get("resolution", "1080p")
        rate = self.COST_PER_MINUTE.get(resolution, 0.40)
        duration = min(prompt.duration_seconds, 10)
        return round((duration / 60.0) * rate, 4)

    def get_max_duration(self) -> int:
        return 10

    def supports_audio_generation(self) -> bool:
        return False

    def supports_reference_images(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "kling"


class RunwayMLAdapter(VideoAPIAdapter):
    """Adapter for Runway Gen-4 API."""

    COST_PER_CLIP = 0.50  # Approximate per clip (Runway charges per generation)

    def format_prompt(self, prompt: VideoPrompt) -> Dict[str, Any]:
        return {
            "text_prompt": prompt.prompt_text,
            "seconds": min(prompt.duration_seconds, 10),
            "aspect_ratio": prompt.aspect_ratio,
            "motion": prompt.motion_intensity,
            "reference_image": prompt.reference_image_path,
        }

    def estimate_cost(self, prompt: VideoPrompt) -> float:
        # Runway typically charges per generation rather than per minute
        return self.COST_PER_CLIP

    def get_max_duration(self) -> int:
        return 10

    def supports_audio_generation(self) -> bool:
        return False

    def supports_reference_images(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "runwayml"


def get_adapter(provider: str) -> VideoAPIAdapter:
    """Factory: get adapter by provider name."""
    adapters = {
        "seedance": SeedanceAdapter,
        "kling": KlingAdapter,
        "runwayml": RunwayMLAdapter,
    }
    if provider not in adapters:
        raise ValueError(f"Unknown API provider: {provider}. Options: {list(adapters.keys())}")
    return adapters[provider]()
