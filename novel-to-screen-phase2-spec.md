# Novel-to-Screen Pipeline — Phase 2 Build Spec
## Script Conversion & Scene Breakdown

**Version:** 1.0  
**Stack:** Python 3.11+  
**Depends on:** Phase 1 output (SQLite DB, ChromaDB, Story Bible JSON)  
**Input:** Phase 1 database + Story Bible  
**Output:** Structured screenplay + scene breakdown JSON  

---

## Overview

Phase 2 takes the Story Bible and narrative chunks from Phase 1 and converts the novel into two things:

1. **A formatted screenplay** — proper INT./EXT. sluglines, action lines, and dialogue in industry-standard structure. Saved as both `.fountain` (plain text screenplay format) and `.json`.
2. **A scene breakdown** — structured per-scene data that Phase 3 will consume to generate video prompts. This is the critical handoff document.

The key challenge here is that novels and screenplays are fundamentally different forms. A novel tells; a screenplay shows. The LLM must be guided to make that translation faithfully — cutting internal monologue, externalising emotion through action and dialogue, and thinking in shots rather than paragraphs.

---

## Project Structure

Extend the existing `novel_pipeline/` from Phase 1:

```
novel_pipeline/
├── ... (Phase 1 files unchanged)
│
├── screenplay/
│   ├── __init__.py
│   ├── converter.py              # Novel chunks → screenplay scenes
│   ├── formatter.py              # Scenes → .fountain format
│   ├── scene_breakdown.py        # Screenplay → structured scene data
│   └── prompts.py                # All Phase 2 LLM prompt templates
│
├── storage/
│   ├── ... (Phase 1 files unchanged)
│   └── schema_phase2.sql         # Additional SQLite tables
│
└── output/
    ├── story_bibles/             # Phase 1 (unchanged)
    ├── screenplays/              # New: .fountain and .json screenplay files
    └── scene_breakdowns/         # New: per-scene structured JSON
```

---

## Additional Dependencies

Add to `requirements.txt`:

```
fountain-py>=0.1.0        # Fountain screenplay format parsing/writing
jinja2>=3.0.0             # Prompt templating
```

---

## Additional SQLite Tables

```sql
-- schema_phase2.sql

CREATE TABLE IF NOT EXISTS screenplays (
    id TEXT PRIMARY KEY,              -- UUID
    novel_id TEXT NOT NULL UNIQUE,
    fountain_text TEXT NOT NULL,      -- Full screenplay in Fountain format
    scene_count INTEGER,
    page_count_estimate INTEGER,      -- ~1 min per page rule of thumb
    created_at TEXT NOT NULL,
    model_used TEXT NOT NULL,
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS screenplay_scenes (
    id TEXT PRIMARY KEY,              -- UUID = scene_id
    screenplay_id TEXT NOT NULL,
    novel_id TEXT NOT NULL,
    scene_number INTEGER NOT NULL,    -- Sequential, 1-indexed
    slug_line TEXT NOT NULL,          -- e.g. "INT. ABANDONED WAREHOUSE - NIGHT"
    location_name TEXT,               -- Normalised to Story Bible location name
    interior_exterior TEXT,           -- "INT" | "EXT" | "INT/EXT"
    time_of_day TEXT,                 -- "DAY" | "NIGHT" | "DAWN" | "DUSK" | "CONTINUOUS"
    action_lines TEXT NOT NULL,       -- The scene's action/description text
    dialogue_json TEXT,               -- JSON array of {character, line, parenthetical}
    characters_present TEXT,          -- JSON array of character names from Story Bible
    scene_type TEXT,                  -- "dialogue", "action", "transition", "montage"
    emotional_beat TEXT,              -- The narrative/emotional purpose of this scene
    source_chunk_ids TEXT,            -- JSON array of Phase 1 chunk_ids this came from
    FOREIGN KEY (screenplay_id) REFERENCES screenplays(id),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);

CREATE TABLE IF NOT EXISTS scene_breakdowns (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL UNIQUE,
    novel_id TEXT NOT NULL,
    breakdown_json TEXT NOT NULL,     -- Full SceneBreakdown serialised as JSON
    created_at TEXT NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES screenplay_scenes(id),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);
```

---

## Module Specifications

---

### 1. `screenplay/prompts.py`

**Purpose:** All LLM prompt templates for Phase 2. Nothing hardcoded elsewhere.

Define the following prompt-building functions:

```python
def novel_to_scene_prompt(
    chunks: list[str],
    story_bible: dict,
    scene_context: str        # Brief description of where we are in the story
) -> str

def scene_breakdown_prompt(
    scene: dict,              # A single screenplay scene
    story_bible: dict
) -> str

def continuity_check_prompt(
    previous_scene: dict,
    current_scene: dict,
    story_bible: dict
) -> str

def act_structure_prompt(
    plot_summary: dict,
    total_chunks: int
) -> str
```

**Critical prompt guidance for `novel_to_scene_prompt`:**

The LLM must be told to:

- Write in **present tense**, active voice throughout (screenplay convention)
- Convert **internal monologue** into visible action, expression, or dialogue subtext — internal thoughts do not exist in screenplays
- Use **proper Fountain syntax**: slug lines (`INT. LOCATION - TIME`), character cues (ALL CAPS), dialogue blocks, parentheticals sparingly
- Keep action lines **visual and concise** — if you can't see it or hear it, cut it
- Do not invent new plot events — stay faithful to the source novel chunks
- Reference the Story Bible for **character names (exact spelling), location names, and period-accurate details**
- Flag scenes where the novel's content may be **difficult to film** (e.g. years of backstory summarised in a paragraph) — mark these as `[ADAPTATION NOTE: ...]` within the action lines
- Aim for approximately **1 screenplay page per scene** for short scenes, up to 3-4 pages for major set pieces
- Think in terms of **what the camera sees**, not what the reader imagines

**Critical prompt guidance for `scene_breakdown_prompt`:**

The LLM must produce a structured breakdown that a video generation system will consume. Tell it to:

- Describe the **visual composition** of the scene's key moment — foreground, midground, background
- Specify **lighting** in cinematographic terms: natural/artificial, hard/soft, direction, colour temperature
- Note **camera movement suggestions**: static, tracking, handheld, crane, etc.
- Identify the **emotional register** the scene must convey and how the visuals support it
- List every character's **exact physical appearance** as per the Story Bible — do not summarise, repeat verbatim so Phase 3 has it inline
- Note any **special requirements**: weather, crowds, specific props, period-accurate details

---

### 2. `screenplay/converter.py`

**Purpose:** Orchestrate the conversion from novel chunks to a full screenplay.

**Class: `ScreenplayConverter`**

```python
class ScreenplayConverter:
    def __init__(self, anthropic_client, db: Database, vector_store: VectorStore, model: str)

    def convert(self, novel_id: str) -> Screenplay
    
    def _load_story_bible(self, novel_id: str) -> StoryBible
    def _load_chunks_sequential(self, novel_id: str) -> list[NarrativeChunk]
    def _determine_act_structure(self, story_bible: StoryBible, chunk_count: int) -> ActStructure
    def _convert_chunk_batch_to_scenes(
        self,
        chunks: list[NarrativeChunk],
        story_bible: StoryBible,
        previous_scene: ScreenplayScene | None,
        act_position: str
    ) -> list[ScreenplayScene]
    def _check_continuity(
        self,
        prev_scene: ScreenplayScene,
        curr_scene: ScreenplayScene,
        story_bible: StoryBible
    ) -> ContinuityCheckResult
    def _renumber_scenes(self, scenes: list[ScreenplayScene]) -> list[ScreenplayScene]
```

**Conversion strategy:**

Process chunks in **overlapping batches of 3** (current + 1 before + 1 after for context). For each batch:

1. Include the Story Bible as system context on every call
2. Include the previous generated scene as context (so the LLM knows where we left off)
3. Note the act position (Act 1 / Act 2A / Act 2B / Act 3) so the LLM can adjust pacing accordingly
4. Generate 1–4 screenplay scenes from the batch
5. Run a lightweight continuity check against the previous scene

**Act structure guidance:**

Use the Story Bible's `plot.acts` to determine rough chunk ranges for each act. Pass the act label into each conversion call so the LLM understands narrative context:
- Act 1 chunks: establish world and characters, slower pacing fine
- Act 2A: rising action, more scene cuts acceptable
- Act 2B (post-midpoint): tension, shorter scenes, faster cuts
- Act 3: climax and resolution, lean and punchy

**Continuity rules to enforce:**
- A character who was last seen in Location A cannot instantly appear in Location B without a travel scene or a time cut
- Time of day must flow logically (DAY → NIGHT → DAY, not random)
- If a character was injured in a previous scene, they carry that injury

---

### 3. `screenplay/formatter.py`

**Purpose:** Convert structured scene data into valid Fountain format text.

**Class: `FountainFormatter`**

```python
class FountainFormatter:
    def format(self, screenplay: Screenplay) -> str
    def format_scene(self, scene: ScreenplayScene) -> str
    def _format_slug_line(self, scene: ScreenplayScene) -> str
    def _format_dialogue_block(self, dialogue: list[DialogueLine]) -> str
    def export_fountain_file(self, screenplay: Screenplay, output_path: str) -> None
    def export_json(self, screenplay: Screenplay, output_path: str) -> None
```

**Fountain format reference:**

```
Title: My Novel Adaptation
Author: [Author from Story Bible]
Draft: First Draft

INT. ABANDONED WAREHOUSE - NIGHT

Rain hammers the corrugated roof. JAMES (40s, lean, haunted eyes)
paces between rusting machinery, phone pressed to his ear.

                    JAMES
          (terse)
     They know. We have maybe an hour.

He ends the call. Stares at the phone.

                    JAMES (CONT'D)
     Maybe less.

CUT TO:
```

**Formatting rules:**
- Slug lines: ALL CAPS, no period at end
- Character cues: ALL CAPS, centred (Fountain handles this via spacing convention)
- Parentheticals: lowercase in brackets, used sparingly (only when delivery is genuinely ambiguous)
- Scene transitions (`CUT TO:`, `DISSOLVE TO:`, `SMASH CUT TO:`) used purposefully, not on every scene
- Page break estimate: 55 lines per page

---

### 4. `screenplay/scene_breakdown.py`

**Purpose:** Take each screenplay scene and generate the rich structured breakdown that Phase 3 needs to build video prompts.

**Class: `SceneBreakdownExtractor`**

```python
class SceneBreakdownExtractor:
    def __init__(self, anthropic_client, db: Database, model: str)
    
    def process_all_scenes(self, novel_id: str) -> list[SceneBreakdown]
    def process_scene(self, scene: ScreenplayScene, story_bible: StoryBible) -> SceneBreakdown
    def _call_llm(self, prompt: str) -> str
```

---

### 5. `extraction/models.py` — Phase 2 Additions

Add the following Pydantic models (extend the Phase 1 file):

```python
class DialogueLine(BaseModel):
    character: str
    line: str
    parenthetical: str | None = None    # e.g. "quietly", "into phone"

class ScreenplayScene(BaseModel):
    scene_id: str                        # UUID
    scene_number: int
    slug_line: str                       # e.g. "INT. BAKERY - DAY"
    interior_exterior: str               # "INT" | "EXT" | "INT/EXT"
    location_name: str                   # Normalised to Story Bible
    time_of_day: str
    action_lines: str
    dialogue: list[DialogueLine]
    characters_present: list[str]        # Names matching Story Bible exactly
    scene_type: str                      # "dialogue" | "action" | "transition" | "montage"
    emotional_beat: str                  # e.g. "James discovers the betrayal"
    adaptation_notes: list[str]          # Any [ADAPTATION NOTE] flags from LLM
    source_chunk_ids: list[str]          # Phase 1 chunk UUIDs

class ActStructure(BaseModel):
    act_one_chunk_range: tuple[int, int]
    act_two_a_chunk_range: tuple[int, int]
    act_two_b_chunk_range: tuple[int, int]
    act_three_chunk_range: tuple[int, int]

class Screenplay(BaseModel):
    screenplay_id: str                   # UUID
    novel_id: str
    novel_title: str
    scenes: list[ScreenplayScene]
    act_structure: ActStructure
    fountain_text: str                   # Full formatted screenplay
    scene_count: int
    page_count_estimate: int
    created_at: str
    model_used: str

class VisualComposition(BaseModel):
    key_moment_description: str          # What the camera shows at the scene's peak
    foreground: str
    midground: str
    background: str
    lighting: str                        # e.g. "Low-key, single practical lamp, warm amber"
    camera_movement: str                 # e.g. "Slow push-in on James's face"
    colour_palette: str                  # e.g. "Desaturated blues and greys, one warm accent"

class SceneBreakdown(BaseModel):
    breakdown_id: str                    # UUID
    scene_id: str                        # FK to ScreenplayScene
    scene_number: int
    slug_line: str
    
    # Story context
    emotional_beat: str
    narrative_purpose: str               # What this scene accomplishes in the story
    
    # Visual specification (feeds directly into Phase 3 video prompts)
    composition: VisualComposition
    characters_with_descriptions: dict[str, str]  # {name: full physical description from Story Bible}
    location_visual_description: str     # Full visual description from Story Bible
    props_and_set_dressing: list[str]    # Specific items that must appear
    
    # Audio hints (for Seedance 2.0 audio generation)
    ambient_sound: str                   # e.g. "Rain on windows, distant traffic"
    dialogue_present: bool
    music_mood: str                      # e.g. "Tense, sparse piano, building strings"
    
    # Production metadata
    special_requirements: list[str]      # Crowd, weather, stunts, VFX etc.
    estimated_clip_count: int            # How many ~10s video clips this scene might need
    continuity_notes: str                # Any flags about props/appearance carrying from prev scene
    
    # Phase 3 ready flag
    prompt_ready: bool                   # True if all required fields are populated
```

---

## CLI Extensions

Add to `main.py`:

```
python main.py convert-script --novel-id <uuid>
python main.py breakdown-scenes --novel-id <uuid>
python main.py phase2 --novel-id <uuid>           # convert-script + breakdown-scenes in one go
python main.py export-script --novel-id <uuid> --format fountain|json|both
python main.py list-scenes --novel-id <uuid>      # Print scene list as a table
```

**`phase2` flow:**
1. Load Story Bible and chunks from Phase 1 DB
2. Determine act structure
3. Convert chunks to screenplay scenes (with progress bar)
4. Run continuity checks between adjacent scenes
5. Format and save Fountain file to `output/screenplays/<title>.fountain`
6. Save screenplay JSON to `output/screenplays/<title>_screenplay.json`
7. Run scene breakdown extraction on all scenes (with progress bar)
8. Save individual scene breakdowns to SQLite
9. Export combined scene breakdown JSON to `output/scene_breakdowns/<title>_breakdown.json`
10. Print summary: scene count, estimated page count, estimated runtime, any adaptation notes flagged

---

## Quality Gates

Before Phase 2 is considered complete for a given novel, check:

- [ ] Every scene has a valid slug line matching Story Bible location names
- [ ] Every character referenced in action/dialogue exists in the Story Bible (warn if not)
- [ ] No scene has an empty `action_lines` field
- [ ] Scene numbers are sequential with no gaps
- [ ] Act structure coverage: chunks are fully covered across all four act ranges
- [ ] All `SceneBreakdown` records have `prompt_ready: True`

Implement a `python main.py validate-phase2 --novel-id <uuid>` command that runs these checks and reports any failures.

---

## Output Artifacts

After a successful `phase2` run, the user has:

1. **Fountain screenplay** at `output/screenplays/<title>.fountain` — human-readable, importable into Final Draft or Highland
2. **Screenplay JSON** at `output/screenplays/<title>_screenplay.json` — structured scene list
3. **Scene breakdown JSON** at `output/scene_breakdowns/<title>_breakdown.json` — the primary Phase 3 input
4. **SQLite tables** `screenplays`, `screenplay_scenes`, `scene_breakdowns` fully populated

---

## Scope Boundaries

Phase 2 explicitly does NOT:

- Generate any video prompts (Phase 3)
- Call any video generation APIs (Phase 4)
- Make creative decisions that deviate significantly from the source novel
- Handle music or sound design beyond mood notes in `SceneBreakdown.music_mood`
- Produce a production budget, shot list, or storyboard

---

## Handoff to Phase 3

Phase 3 (Prompt Engineering) will consume the `scene_breakdowns/<title>_breakdown.json` file.

The fields Phase 3 relies on most heavily are:

- `composition` — the entire `VisualComposition` object becomes the structural backbone of the video prompt
- `characters_with_descriptions` — inlined per scene so Phase 3 never needs to look up the Story Bible separately
- `location_visual_description` — same principle, inlined for convenience
- `ambient_sound` + `music_mood` — fed into Seedance 2.0's audio generation parameters
- `estimated_clip_count` — tells Phase 3 how many API calls to plan for this scene
- `props_and_set_dressing` — ensures visual consistency between clips within a scene

**The guiding principle for Phase 2:** every field in `SceneBreakdown` should be so specific and self-contained that Phase 3 can generate a high-quality video prompt without ever needing to re-read the original novel or Story Bible.

---

*Build spec authored for Novel-to-Screen Pipeline, Phase 2.*  
*Prev: Phase 1 — Novel Ingestion & Story Bible Extraction*  
*Next: Phase 3 — Video Prompt Engineering*
