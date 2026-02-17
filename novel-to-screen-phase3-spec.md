# Novel-to-Screen Pipeline — Phase 3 Build Spec
## Video Prompt Engineering & Generation Orchestration

**Version:** 1.0  
**Stack:** Python 3.11+  
**Depends on:** Phase 2 output (Scene Breakdown JSON)  
**Input:** Scene breakdown JSON + Story Bible  
**Output:** Structured video generation job queue + prompt library  

---

## Overview

Phase 3 is the translation layer between screenplay and video. It takes the `SceneBreakdown` objects from Phase 2 and engineers high-quality prompts for video generation APIs.

This phase does NOT actually call video generation APIs - that's Phase 4. Phase 3's job is pure prompt engineering and job queue preparation. The separation is deliberate:

- Prompts can be reviewed, tweaked, and regenerated without burning API credits
- Multiple prompts per scene can be generated and A/B tested
- The job queue can be executed incrementally (useful when video gen is slow/expensive)
- Prompts can be re-targeted to different video APIs without rebuilding the whole pipeline

**Key principle:** The prompts must be self-contained. Each prompt should work perfectly even if someone copy-pastes it into a web UI with zero additional context.

---

## Project Structure

Extend `novel_pipeline/`:

```
novel_pipeline/
├── ... (Phase 1 & 2 files unchanged)
│
├── prompts/
│   ├── __init__.py
│   ├── video_prompt_engineer.py      # Core prompt generation logic
│   ├── templates.py                  # Prompt template library
│   ├── reference_manager.py          # Manage character/location reference images
│   └── validators.py                 # Prompt quality checks
│
├── generation/
│   ├── __init__.py
│   ├── job_queue.py                  # Video generation job queue
│   ├── api_adapters.py               # Abstract API layer (Seedance, Kling, etc.)
│   └── cost_estimator.py             # Pre-generation cost estimation
│
├── storage/
│   ├── ... (Phase 1 & 2 files unchanged)
│   └── schema_phase3.sql             # Job queue and prompt tables
│
└── output/
    ├── prompts/                      # Generated video prompts as JSON/text
    ├── reference_images/             # Character/location reference images (if used)
    └── jobs/                         # Serialised job queue for Phase 4
```

---

## Additional Dependencies

```
pillow>=10.0.0           # Image manipulation for reference images
requests>=2.31.0         # API preparation (not actual calls yet)
pyyaml>=6.0              # Prompt template configuration
```

---

## Additional SQLite Tables

```sql
-- schema_phase3.sql

CREATE TABLE IF NOT EXISTS video_prompts (
    id TEXT PRIMARY KEY,                    -- UUID = prompt_id
    scene_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    clip_index INTEGER NOT NULL,            -- Position within scene (0-indexed)
    prompt_type TEXT NOT NULL,              -- "establishing" | "action" | "dialogue" | "transition" | "reaction"
    prompt_text TEXT NOT NULL,              -- The actual prompt for the video API
    negative_prompt TEXT,                   -- What NOT to generate
    duration_seconds INTEGER NOT NULL,      -- Target clip length (4-15s for Seedance 2.0)
    aspect_ratio TEXT,                      -- "16:9" | "9:16" | "1:1"
    motion_intensity TEXT,                  -- "low" | "medium" | "high"
    camera_movement TEXT,                   -- "static" | "pan" | "tilt" | "dolly" | "handheld"
    reference_image_path TEXT,              -- Path to reference image (if used)
    character_consistency_tags TEXT,        -- JSON array of character appearance anchors
    audio_prompt TEXT,                      -- Audio generation guidance (for Seedance 2.0)
    generation_params TEXT,                 -- JSON object of API-specific parameters
    estimated_cost_usd REAL,                -- Pre-computed cost estimate
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,                    -- UUID = job_id
    prompt_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    clip_index INTEGER NOT NULL,
    status TEXT DEFAULT 'queued',           -- "queued" | "running" | "complete" | "failed" | "skipped"
    api_provider TEXT NOT NULL,             -- "seedance" | "kling" | "runwayml"
    api_job_id TEXT,                        -- Provider's job ID (set in Phase 4)
    output_video_path TEXT,                 -- Path to generated video (set in Phase 4)
    generation_time_seconds INTEGER,        -- Actual generation time (set in Phase 4)
    actual_cost_usd REAL,                   -- Actual cost (set in Phase 4)
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (prompt_id) REFERENCES video_prompts(id)
);

CREATE TABLE IF NOT EXISTS prompt_iterations (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    clip_index INTEGER NOT NULL,
    iteration INTEGER NOT NULL,             -- Version number of this prompt
    prompt_text TEXT NOT NULL,
    notes TEXT,                             -- Why this iteration was created
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id)
);
```

---

## Module Specifications

---

### 1. `prompts/templates.py`

**Purpose:** Define reusable prompt templates with clear slot-filling patterns.

Provide a template library that covers the major shot types:

```python
class PromptTemplates:
    """
    Template structure philosophy:
    - Start with WHAT (subject/action)
    - Then WHERE (setting/environment)
    - Then HOW (camera, lighting, mood)
    - Then STYLE (cinematic references, technical specs)
    """
    
    @staticmethod
    def establishing_shot(
        location: str,
        time_of_day: str,
        weather: str,
        atmosphere: str,
        era: str
    ) -> str:
        """
        Wide shot establishing location.
        Typically the first clip in a new scene.
        """
        pass
    
    @staticmethod
    def character_introduction(
        character_name: str,
        physical_description: str,
        action: str,
        location_context: str,
        lighting: str,
        mood: str
    ) -> str:
        """
        First appearance of a character in a scene.
        """
        pass
    
    @staticmethod
    def dialogue_two_shot(
        char1_name: str,
        char1_desc: str,
        char2_name: str,
        char2_desc: str,
        emotional_dynamic: str,
        setting_detail: str,
        lighting: str
    ) -> str:
        """
        Two characters in frame, dialogue exchange.
        """
        pass
    
    @staticmethod
    def dialogue_over_shoulder(
        speaking_char: str,
        speaking_char_desc: str,
        listening_char: str,
        listening_char_desc: str,
        emotional_beat: str,
        background: str
    ) -> str:
        """
        Over-the-shoulder shot during dialogue.
        Focus on listener's reaction.
        """
        pass
    
    @staticmethod
    def action_sequence(
        action_description: str,
        environment: str,
        camera_movement: str,
        motion_intensity: str,
        lighting: str,
        sound_design_hint: str
    ) -> str:
        """
        Dynamic action - chase, fight, physical movement.
        """
        pass
    
    @staticmethod
    def reaction_close_up(
        character_name: str,
        character_desc: str,
        emotion: str,
        micro_expression: str,
        lighting: str
    ) -> str:
        """
        Close-up on character's face capturing emotional response.
        """
        pass
    
    @staticmethod
    def transition_shot(
        from_location: str,
        to_location: str,
        transition_type: str,       # "cut" | "dissolve" | "match_cut"
        time_passage: str            # "none" | "minutes" | "hours" | "days"
    ) -> str:
        """
        Visual bridge between scenes or locations.
        """
        pass
    
    @staticmethod
    def montage_clip(
        activity: str,
        setting: str,
        progression_note: str,       # e.g. "third beat in a training montage"
        music_sync_hint: str
    ) -> str:
        """
        Single clip in a montage sequence.
        """
        pass
    
    @staticmethod
    def insert_shot(
        object_focus: str,
        significance: str,
        framing: str,
        lighting: str
    ) -> str:
        """
        Detail shot of an object/prop with narrative importance.
        """
        pass
```

**Template design principles:**

- **Be specific about the subject** - "A weathered man in his 40s with grey-streaked hair" not "a man"
- **Use cinematographic language** - "low-key lighting from a single desk lamp" not "dark room"
- **Include temporal cues** - "slow push-in" not just "camera movement"
- **Reference visual style** - Can include phrases like "shot on 35mm film, shallow depth of field, anamorphic bokeh" to guide the model's aesthetic
- **Character consistency anchors** - Always include 2-3 distinctive physical features per character every time they appear

**Negative prompt patterns:**

Common things to exclude:
- Unrealistic physics
- Morphing/distortion of faces or hands
- Text/logos appearing randomly
- Anachronistic elements (modern cars in period pieces)
- Multiple copies of the same character in frame
- Blurriness or low resolution artifacts

---

### 2. `prompts/video_prompt_engineer.py`

**Purpose:** Core logic for generating video prompts from scene breakdowns.

**Class: `VideoPromptEngineer`**

```python
class VideoPromptEngineer:
    def __init__(self, db: Database, templates: PromptTemplates)
    
    def generate_prompts_for_scene(
        self,
        scene_breakdown: SceneBreakdown,
        story_bible: StoryBible
    ) -> list[VideoPrompt]
    
    def _determine_shot_sequence(self, scene_breakdown: SceneBreakdown) -> list[ShotSpec]
    def _build_prompt_from_shot_spec(
        self,
        shot_spec: ShotSpec,
        scene_breakdown: SceneBreakdown,
        story_bible: StoryBible
    ) -> VideoPrompt
    def _extract_character_appearance_tags(self, character_name: str, story_bible: StoryBible) -> list[str]
    def _build_negative_prompt(self, scene_breakdown: SceneBreakdown) -> str
    def _build_audio_prompt(self, scene_breakdown: SceneBreakdown) -> str
    def _estimate_clip_duration(self, shot_type: str, scene_breakdown: SceneBreakdown) -> int
```

**Shot sequence logic:**

For a given scene, determine the sequence of clips needed:

1. **Establishing shot** (if new location or time jump from previous scene)
2. **Character introductions** (for each character appearing for first time in scene)
3. **Dialogue coverage** (if dialogue present):
   - Wide two-shot
   - Over-shoulder on Speaker A
   - Over-shoulder on Speaker B  
   - Reaction close-ups as needed
4. **Action beats** (one clip per distinct action from the scene breakdown)
5. **Transition shot** (if scene ends with explicit movement or time passage)

**Shot type selection rules:**

- Dialogue-heavy scenes: favour two-shots and over-shoulders
- Action sequences: more frequent cuts, dynamic camera movement
- Emotional beats: close-ups and reaction shots
- Location establishment: wide shots with environmental detail
- Transitions: match cuts or visual metaphors when appropriate

**Character consistency strategy:**

For each character appearance, include:
- Full name (as per Story Bible)
- 2-3 distinctive physical anchors (e.g. "scar above left eyebrow, silver wedding ring, grey-streaked beard")
- Clothing description (if specified in scene breakdown)
- Age decade (e.g. "late 40s")

These anchors get repeated **verbatim** across all clips in which the character appears. This is critical for Seedance 2.0's character consistency features.

**Duration calculation:**

- Establishing shots: 6-8 seconds
- Dialogue clips: 8-12 seconds (need time for lines to be spoken)
- Action beats: 4-8 seconds (faster cuts build tension)
- Reaction shots: 3-5 seconds (brief emotional punctuation)
- Transition shots: 4-6 seconds

Total scene duration = sum of clip durations. Aim for scenes to land between 30s - 2min total.

---

### 3. `prompts/reference_manager.py`

**Purpose:** Handle generation and management of reference images for character/location consistency.

**Class: `ReferenceManager`**

```python
class ReferenceManager:
    def __init__(self, output_path: str)
    
    def create_character_reference(
        self,
        character_profile: CharacterProfile,
        image_source: str | None = None    # Optional: user-provided image path
    ) -> str
    
    def create_location_reference(
        self,
        location: Location,
        image_source: str | None = None
    ) -> str
    
    def attach_reference_to_prompt(
        self,
        prompt: VideoPrompt,
        reference_path: str
    ) -> VideoPrompt
```

**Reference image strategy:**

Seedance 2.0 supports uploading reference images for character/location consistency. Two approaches:

**Option A: User-provided images**  
If the user has concept art, storyboards, or AI-generated reference images, they can provide those. The `ReferenceManager` validates and stores them.

**Option B: Generate reference images**  
If no references exist, Phase 3 can optionally call an image generation API (DALL-E, Midjourney, Stable Diffusion) to create reference images from the Story Bible descriptions. This is outside core scope but hooks should be in place.

For now, assume **Option A** - user provides references or we skip them. Reference images are optional, not required.

---

### 4. `prompts/validators.py`

**Purpose:** Quality checks on generated prompts before they enter the job queue.

**Class: `PromptValidator`**

```python
class PromptValidator:
    @staticmethod
    def validate_prompt(prompt: VideoPrompt) -> ValidationResult
    
    @staticmethod
    def check_character_consistency(
        prompts: list[VideoPrompt],
        character_name: str
    ) -> ConsistencyReport
    
    @staticmethod
    def check_prompt_length(prompt_text: str) -> bool
    
    @staticmethod
    def detect_anachronisms(prompt_text: str, era: str) -> list[str]
    
    @staticmethod
    def check_temporal_coherence(
        prompts: list[VideoPrompt],
        scene_breakdown: SceneBreakdown
    ) -> TemporalReport
```

**Validation rules:**

- **Prompt length**: Most video APIs have token limits (~500 tokens). Flag prompts exceeding this.
- **Character consistency**: All prompts featuring the same character should use identical physical description anchors.
- **Temporal coherence**: Time of day should flow logically across sequential clips (DAY → DUSK → NIGHT, not random).
- **Anachronism detection**: Check for modern terms in period pieces (e.g. "smartphone" in a 1920s scene).
- **Missing required fields**: Every prompt must have `duration_seconds`, `prompt_text`, and `scene_id`.

Validators return structured reports, not just pass/fail booleans. The user should see *what* failed and *why*.

---

### 5. `generation/job_queue.py`

**Purpose:** Manage the queue of video generation jobs that Phase 4 will execute.

**Class: `JobQueue`**

```python
class JobQueue:
    def __init__(self, db: Database)
    
    def add_job(self, prompt: VideoPrompt, api_provider: str) -> GenerationJob
    def get_next_job(self, api_provider: str | None = None) -> GenerationJob | None
    def mark_running(self, job_id: str) -> None
    def mark_complete(self, job_id: str, output_path: str, cost: float, duration: int) -> None
    def mark_failed(self, job_id: str, error: str) -> None
    def get_queue_stats(self, novel_id: str) -> QueueStats
    def export_queue(self, novel_id: str, output_path: str) -> None
```

**Job queue design:**

- Jobs are stored in SQLite (persistent, survives process crashes)
- Jobs can be filtered by API provider (useful if user wants Kling for some scenes, Seedance for others)
- Queue is FIFO within each scene (preserve shot order)
- Between scenes, prioritise by scene_number (sequential narrative flow)

**Queue statistics:**

```python
class QueueStats(BaseModel):
    total_jobs: int
    queued: int
    running: int
    complete: int
    failed: int
    estimated_total_cost_usd: float
    estimated_total_duration_minutes: int
```

---

### 6. `generation/api_adapters.py`

**Purpose:** Abstract API layer so prompts can be re-targeted to different video generation providers.

Define an abstract base class:

```python
class VideoAPIAdapter(ABC):
    @abstractmethod
    def format_prompt(self, prompt: VideoPrompt) -> dict:
        """Convert VideoPrompt to provider-specific API request format"""
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt: VideoPrompt) -> float:
        """Estimate generation cost in USD"""
        pass
    
    @abstractmethod
    def get_max_duration(self) -> int:
        """Max clip length in seconds for this provider"""
        pass
    
    @abstractmethod
    def supports_audio_generation(self) -> bool:
        """Whether provider generates audio natively"""
        pass
    
    @abstractmethod
    def supports_reference_images(self) -> bool:
        """Whether provider accepts reference images for consistency"""
        pass

class SeedanceAdapter(VideoAPIAdapter):
    """Adapter for Seedance 2.0 API (ByteDance)"""
    pass

class KlingAdapter(VideoAPIAdapter):
    """Adapter for Kling API (Kuaishou)"""
    pass

class RunwayMLAdapter(VideoAPIAdapter):
    """Adapter for Runway Gen-4 API"""
    pass
```

**Implementation notes:**

Phase 3 does NOT call these APIs. It only uses the adapters to:
- Format prompts correctly for the target API
- Estimate costs
- Validate that prompt parameters are within API limits (e.g. max duration)

The actual API calls happen in Phase 4.

---

### 7. `generation/cost_estimator.py`

**Purpose:** Pre-generation cost estimation for budget planning.

**Class: `CostEstimator`**

```python
class CostEstimator:
    def __init__(self, api_adapter: VideoAPIAdapter)
    
    def estimate_scene_cost(self, scene_prompts: list[VideoPrompt]) -> float
    def estimate_novel_cost(self, novel_id: str) -> CostBreakdown
    def compare_providers(self, prompts: list[VideoPrompt]) -> dict[str, float]
```

**Cost calculation (approximate for Seedance 2.0):**

Based on the search results from earlier:
- 720p Basic: ~$0.10 per minute
- 1080p Standard: ~$0.30 per minute  
- 2K Cinema: ~$0.80 per minute

For a 90-minute novel adapted to 30 minutes of video at 1080p Standard:
- 30 min × $0.30/min = **~$9 USD**

Much cheaper than Sora 2 which is ~$3-10 per clip.

**Cost breakdown report:**

```python
class CostBreakdown(BaseModel):
    total_clips: int
    total_duration_minutes: float
    estimated_cost_usd: float
    breakdown_by_scene: dict[str, float]
    breakdown_by_resolution: dict[str, float]
```

---

### 8. Pydantic Models — Phase 3 Additions

```python
class ShotSpec(BaseModel):
    shot_type: str              # "establishing" | "character_intro" | "dialogue_two_shot" | "action" | "reaction" | "transition" | "insert"
    clip_index: int             # Position in scene
    characters: list[str]       # Character names
    camera_movement: str
    framing: str                # "wide" | "medium" | "close_up" | "extreme_close_up"
    duration_seconds: int

class VideoPrompt(BaseModel):
    prompt_id: str              # UUID
    scene_id: str
    novel_id: str
    clip_index: int
    prompt_type: str
    prompt_text: str            # The actual prompt
    negative_prompt: str
    duration_seconds: int
    aspect_ratio: str           # "16:9" | "9:16" | "1:1"
    motion_intensity: str       # "low" | "medium" | "high"
    camera_movement: str
    reference_image_path: str | None
    character_consistency_tags: list[str]
    audio_prompt: str
    generation_params: dict     # API-specific params (resolution, etc.)
    estimated_cost_usd: float
    created_at: str

class GenerationJob(BaseModel):
    job_id: str                 # UUID
    prompt_id: str
    novel_id: str
    scene_id: str
    clip_index: int
    status: str                 # "queued" | "running" | "complete" | "failed"
    api_provider: str           # "seedance" | "kling" | "runwayml"
    api_job_id: str | None
    output_video_path: str | None
    generation_time_seconds: int | None
    actual_cost_usd: float | None
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None

class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str]
    warnings: list[str]

class ConsistencyReport(BaseModel):
    character_name: str
    total_appearances: int
    consistent_descriptions: bool
    discrepancies: list[str]

class TemporalReport(BaseModel):
    is_coherent: bool
    issues: list[str]

class QueueStats(BaseModel):
    total_jobs: int
    queued: int
    running: int
    complete: int
    failed: int
    estimated_total_cost_usd: float
    estimated_total_duration_minutes: int
```

---

## CLI Extensions

Add to `main.py`:

```
python main.py generate-prompts --novel-id <uuid> [--api seedance|kling]
python main.py validate-prompts --novel-id <uuid>
python main.py estimate-cost --novel-id <uuid> [--api seedance|kling]
python main.py compare-apis --novel-id <uuid>
python main.py export-prompts --novel-id <uuid> --output ./prompts.json
python main.py create-job-queue --novel-id <uuid> --api seedance
python main.py phase3 --novel-id <uuid> --api seedance    # Full Phase 3 pipeline
```

**`phase3` flow:**

1. Load scene breakdowns from Phase 2
2. Load Story Bible from Phase 1
3. For each scene, generate prompts (with progress bar)
4. Run validation on all prompts
5. Save prompts to SQLite `video_prompts` table
6. Build job queue for selected API provider
7. Run cost estimation
8. Export prompts JSON to `output/prompts/<title>_prompts.json`
9. Export job queue to `output/jobs/<title>_<api>_queue.json`
10. Print summary:
    - Total clips: X
    - Total estimated duration: X minutes
    - Estimated cost: $X USD
    - Validation warnings: X
    - Job queue ready for Phase 4: Yes/No

---

## Quality Gates

Before Phase 3 is considered complete:

- [ ] Every scene has at least one prompt
- [ ] No prompts exceed token limits for target API
- [ ] All prompts pass validation with zero errors (warnings acceptable)
- [ ] Character consistency check passes across all scenes
- [ ] Temporal coherence check passes within each scene
- [ ] Job queue is properly ordered (scene → clip index)
- [ ] Cost estimate is within expected range (flag if >2x expected)

---

## Output Artifacts

After `phase3` completes:

1. **Prompts JSON** at `output/prompts/<title>_prompts.json` - all generated prompts
2. **Job queue JSON** at `output/jobs/<title>_<api>_queue.json` - execution-ready queue for Phase 4
3. **Cost estimate report** printed to console and saved to SQLite
4. **Validation report** flagging any issues
5. **SQLite tables** `video_prompts` and `generation_jobs` fully populated

---

## Prompt Quality Examples

### Good Prompt (Character Introduction)

```
Medium shot of DETECTIVE SARAH CHEN (late 30s, sharp brown eyes, cropped black hair with grey streak on right temple, navy wool coat over white button-down shirt) standing in front of a rain-streaked window. She stares at a case file in her hands, jaw clenched. Low-key lighting from a single desk lamp creates hard shadows across her face. Background: blurred city lights through wet glass, neon signs reflecting in puddles. Shot on 35mm film, shallow depth of field, desaturated colour palette with amber accents. Slow push-in on her face as she closes the file.
```

**Why it works:**
- Specific physical anchors (grey streak, navy coat)
- Clear action (staring at file, jaw clenched)
- Detailed lighting (low-key, desk lamp, hard shadows)
- Environmental context (rain, city, neon)
- Camera movement (slow push-in)
- Style notes (35mm, shallow DOF, colour palette)

### Bad Prompt

```
A detective looks at some papers in an office. Dark lighting. She looks serious.
```

**Why it fails:**
- Generic description ("a detective")
- No physical details
- Vague lighting
- No camera guidance
- No style or mood
- Won't maintain character consistency across clips

---

## Scope Boundaries

Phase 3 explicitly does NOT:

- Call any video generation APIs (Phase 4)
- Edit or stitch together generated videos (Phase 4)
- Add music or sound effects (Phase 4)
- Perform upscaling or post-processing (Phase 4)
- Generate reference images (optional enhancement, not core)

---

## Handoff to Phase 4

Phase 4 (Video Generation Execution) consumes:

1. The `generation_jobs` table from SQLite (or exported JSON queue)
2. The `video_prompts` table for full prompt details
3. Any reference images from `output/reference_images/`

Phase 4's job is to:
- Execute the job queue against the actual APIs
- Handle retries and rate limiting
- Download and store generated videos
- Update job status in the database
- Stitch clips together per scene

**The guiding principle for Phase 3:** Every prompt should be so well-crafted that even if the user copy-pasted it into Seedance's web UI manually, it would produce a high-quality clip that fits the scene. The prompts are the product, not just an implementation detail.

---

*Build spec authored for Novel-to-Screen Pipeline, Phase 3.*  
*Prev: Phase 2 — Script Conversion & Scene Breakdown*  
*Next: Phase 4 — Video Generation & Assembly*
