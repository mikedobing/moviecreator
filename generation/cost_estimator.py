"""
Cost estimator for video generation.

Pre-generation cost estimation for budget planning.
Uses API adapter pricing to calculate estimates per scene and per novel.
"""

from typing import List, Dict
from extraction.models import VideoPrompt, CostBreakdown
from generation.api_adapters import VideoAPIAdapter, get_adapter


class CostEstimator:
    """Estimate video generation costs before committing API credits."""

    def __init__(self, api_provider: str = "seedance"):
        self.adapter = get_adapter(api_provider)
        self.provider = api_provider

    def estimate_scene_cost(self, scene_prompts: List[VideoPrompt]) -> float:
        """Estimate total cost for all clips in a scene."""
        return sum(self.adapter.estimate_cost(p) for p in scene_prompts)

    def estimate_novel_cost(self, prompts: List[VideoPrompt]) -> CostBreakdown:
        """Compute detailed cost breakdown for all prompts in a novel."""
        # Group by scene
        scene_prompts: Dict[str, List[VideoPrompt]] = {}
        for prompt in prompts:
            scene_prompts.setdefault(prompt.scene_id, []).append(prompt)

        breakdown_by_scene = {}
        for scene_id, sp in scene_prompts.items():
            breakdown_by_scene[scene_id] = round(
                sum(self.adapter.estimate_cost(p) for p in sp), 4
            )

        # Group by resolution
        resolution_costs: Dict[str, float] = {}
        for prompt in prompts:
            res = prompt.generation_params.get("resolution", "1080p")
            cost = self.adapter.estimate_cost(prompt)
            resolution_costs[res] = resolution_costs.get(res, 0) + cost

        total_duration = sum(p.duration_seconds for p in prompts)
        total_cost = sum(breakdown_by_scene.values())

        return CostBreakdown(
            total_clips=len(prompts),
            total_duration_minutes=round(total_duration / 60.0, 1),
            estimated_cost_usd=round(total_cost, 2),
            breakdown_by_scene={k: round(v, 2) for k, v in breakdown_by_scene.items()},
            breakdown_by_resolution={k: round(v, 2) for k, v in resolution_costs.items()},
        )

    def compare_providers(self, prompts: List[VideoPrompt]) -> Dict[str, float]:
        """Compare estimated cost across all supported providers."""
        providers = ["seedance", "kling", "runwayml"]
        comparison = {}
        for provider in providers:
            adapter = get_adapter(provider)
            total = sum(adapter.estimate_cost(p) for p in prompts)
            comparison[provider] = round(total, 2)
        return comparison
