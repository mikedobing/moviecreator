"""Pydantic models for Story Bible extraction."""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class CharacterProfile(BaseModel):
    """Character information extracted from novel."""
    name: str
    aliases: List[str] = Field(default_factory=list)
    role: str  # protagonist, antagonist, supporting, minor
    physical_description: str
    personality: str
    backstory_summary: str
    relationships: Dict[str, str] = Field(default_factory=dict)
    first_appearance_chunk: str = ""
    notable_quotes: List[str] = Field(default_factory=list)


class Location(BaseModel):
    """Location information extracted from novel."""
    name: str
    location_type: str  # interior, exterior, urban, rural, fantasy, etc.
    visual_description: str
    atmosphere: str
    associated_characters: List[str] = Field(default_factory=list)
    significance: str


class TimelinePeriod(BaseModel):
    """Time period and setting information."""
    description: str
    era: str
    technology_level: str
    cultural_notes: str


class NarrativeTone(BaseModel):
    """Overall tone and style of the narrative."""
    genre: List[str] = Field(default_factory=list)
    mood: str
    pacing: str
    style_notes: str
    violence_level: str
    content_warnings: List[str] = Field(default_factory=list)


class PlotSummary(BaseModel):
    """Plot summary and structure."""
    logline: str
    synopsis: str
    acts: List[str] = Field(default_factory=list)
    key_themes: List[str] = Field(default_factory=list)


class StoryBible(BaseModel):
    """Complete Story Bible extracted from novel."""
    novel_title: str
    extraction_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    characters: List[CharacterProfile] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    timeline: TimelinePeriod
    tone: NarrativeTone
    plot: PlotSummary
    world_rules: List[str] = Field(default_factory=list)
    visual_style_notes: str = ""


# ==================== Phase 2 Models ====================

class DialogueLine(BaseModel):
    """A line of dialogue in a screenplay."""
    character: str
    line: str
    parenthetical: Optional[str] = None  # e.g. "quietly", "into phone"


class ScreenplayScene(BaseModel):
    """A single scene in the screenplay."""
    scene_id: str  # UUID
    scene_number: int
    slug_line: str  # e.g. "INT. BAKERY - DAY"
    interior_exterior: str  # "INT" | "EXT" | "INT/EXT"
    location_name: str  # Normalised to Story Bible
    time_of_day: str
    action_lines: str
    dialogue: List[DialogueLine] = Field(default_factory=list)
    characters_present: List[str] = Field(default_factory=list)  # Names matching Story Bible exactly
    scene_type: str  # "dialogue" | "action" | "transition" | "montage"
    emotional_beat: str  # e.g. "James discovers the betrayal"
    adaptation_notes: List[str] = Field(default_factory=list)  # Any [ADAPTATION NOTE] flags from LLM
    source_chunk_ids: List[str] = Field(default_factory=list)  # Phase 1 chunk UUIDs


class ActStructure(BaseModel):
    """Act structure boundaries for the screenplay."""
    act_one_chunk_range: Tuple[int, int]
    act_two_a_chunk_range: Tuple[int, int]
    act_two_b_chunk_range: Tuple[int, int]
    act_three_chunk_range: Tuple[int, int]


class Screenplay(BaseModel):
    """Complete screenplay with all scenes."""
    screenplay_id: str  # UUID
    novel_id: str
    novel_title: str
    scenes: List[ScreenplayScene] = Field(default_factory=list)
    act_structure: ActStructure
    fountain_text: str = ""  # Full formatted screenplay
    scene_count: int = 0
    page_count_estimate: int = 0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    model_used: str = ""


class VisualComposition(BaseModel):
    """Visual composition details for a scene."""
    key_moment_description: str  # What the camera shows at the scene's peak
    foreground: str
    midground: str
    background: str
    lighting: str  # e.g. "Low-key, single practical lamp, warm amber"
    camera_movement: str  # e.g. "Slow push-in on James's face"
    colour_palette: str  # e.g. "Desaturated blues and greys, one warm accent"


class SceneBreakdown(BaseModel):
    """Detailed scene breakdown for video generation (Phase 3 input)."""
    breakdown_id: str  # UUID
    scene_id: str  # FK to ScreenplayScene
    scene_number: int
    slug_line: str
    
    # Story context
    emotional_beat: str
    narrative_purpose: str  # What this scene accomplishes in the story
    
    # Visual specification (feeds directly into Phase 3 video prompts)
    composition: VisualComposition
    characters_with_descriptions: Dict[str, str] = Field(default_factory=dict)  # {name: full physical description from Story Bible}
    location_visual_description: str = ""  # Full visual description from Story Bible
    props_and_set_dressing: List[str] = Field(default_factory=list)  # Specific items that must appear
    
    # Audio hints (for Seedance 2.0 audio generation)
    ambient_sound: str = ""  # e.g. "Rain on windows, distant traffic"
    dialogue_present: bool = False
    music_mood: str = ""  # e.g. "Tense, sparse piano, building strings"
    
    # Production metadata
    special_requirements: List[str] = Field(default_factory=list)  # Crowd, weather, stunts, VFX etc.
    estimated_clip_count: int = 1  # How many ~10s video clips this scene might need
    continuity_notes: str = ""  # Any flags about props/appearance carrying from prev scene
    
    # Phase 3 ready flag
    prompt_ready: bool = False  # True if all required fields are populated


# ==================== Phase 3 Models ====================

class ShotSpec(BaseModel):
    """Specification for a single shot/clip in a scene."""
    shot_type: str  # "establishing" | "character_intro" | "dialogue_two_shot" | "dialogue_over_shoulder" | "action" | "reaction" | "transition" | "insert" | "montage"
    clip_index: int  # Position in scene (0-indexed)
    characters: List[str] = Field(default_factory=list)  # Character names in this shot
    camera_movement: str = "static"  # "static" | "pan" | "tilt" | "dolly" | "push_in" | "pull_back" | "handheld" | "tracking"
    framing: str = "medium"  # "wide" | "medium" | "close_up" | "extreme_close_up"
    duration_seconds: int = 8
    description: str = ""  # Brief description of what happens


class VideoPrompt(BaseModel):
    """A complete video generation prompt for a single clip."""
    prompt_id: str  # UUID
    scene_id: str
    novel_id: str
    clip_index: int
    prompt_type: str  # "establishing" | "character_intro" | "dialogue" | "action" | "reaction" | "transition" | "insert" | "montage"
    prompt_text: str  # The actual prompt for the video API
    negative_prompt: str = ""  # What NOT to generate
    duration_seconds: int = 8  # Target clip length
    aspect_ratio: str = "16:9"  # "16:9" | "9:16" | "1:1"
    motion_intensity: str = "medium"  # "low" | "medium" | "high"
    camera_movement: str = "static"
    reference_image_path: Optional[str] = None
    character_consistency_tags: List[str] = Field(default_factory=list)  # Character appearance anchors
    audio_prompt: str = ""  # Audio generation guidance
    generation_params: Dict = Field(default_factory=dict)  # API-specific params
    estimated_cost_usd: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class GenerationJob(BaseModel):
    """A video generation job for Phase 4 execution."""
    job_id: str  # UUID
    prompt_id: str
    novel_id: str
    scene_id: str
    clip_index: int
    status: str = "queued"  # "queued" | "running" | "complete" | "failed" | "skipped"
    api_provider: str = "seedance"  # "seedance" | "kling" | "runwayml"
    api_job_id: Optional[str] = None
    output_video_path: Optional[str] = None
    generation_time_seconds: Optional[int] = None
    actual_cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of prompt validation."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ConsistencyReport(BaseModel):
    """Character consistency check result."""
    character_name: str
    total_appearances: int
    consistent_descriptions: bool
    discrepancies: List[str] = Field(default_factory=list)


class TemporalReport(BaseModel):
    """Temporal coherence check result."""
    is_coherent: bool
    issues: List[str] = Field(default_factory=list)


class QueueStats(BaseModel):
    """Statistics for the generation job queue."""
    total_jobs: int
    queued: int = 0
    running: int = 0
    complete: int = 0
    failed: int = 0
    estimated_total_cost_usd: float = 0.0
    estimated_total_duration_minutes: float = 0.0


class CostBreakdown(BaseModel):
    """Detailed cost estimation breakdown."""
    total_clips: int
    total_duration_minutes: float
    estimated_cost_usd: float
    breakdown_by_scene: Dict[str, float] = Field(default_factory=dict)
    breakdown_by_resolution: Dict[str, float] = Field(default_factory=dict)

