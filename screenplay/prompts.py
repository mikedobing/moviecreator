"""LLM prompt templates for Phase 2 screenplay conversion."""
from typing import List, Dict, Any
import json


def novel_to_scene_prompt(
    chunks: List[str],
    story_bible: Dict[str, Any],
    scene_context: str,
    previous_scene: Dict[str, Any] | None,
    act_position: str
) -> str:
    """Generate prompt to convert novel chunks to screenplay scenes.
    
    Args:
        chunks: List of narrative chunk texts (typically 3: prev, current, next)
        story_bible: Complete Story Bible dictionary
        scene_context: Brief description of where we are in the story
        previous_scene: Last generated scene for continuity (or None if first scene)
        act_position: "Act 1", "Act 2A", "Act 2B", or "Act 3"
    
    Returns:
        LLM prompt string
    """
    # Extract key Story Bible info
    characters_summary = "\n".join([
        f"- {char['name']}: {char['role']}, {char['physical_description'][:100]}..."
        for char in story_bible.get('characters', [])[:10]  # Top 10 most important
    ])
    
    locations_summary = "\n".join([
       f"- {loc['name']}: {loc['visual_description'][:100]}..."
        for loc in story_bible.get('locations', [])[:10]
    ])
    
    # Previous scene context
    prev_scene_info = ""
    if previous_scene:
        prev_scene_info = f"""
**PREVIOUS SCENE FOR CONTINUITY:**
Scene {previous_scene['scene_number']}: {previous_scene['slug_line']}
Location: {previous_scene['location_name']}
Time: {previous_scene['time_of_day']}
Characters present: {', '.join(previous_scene['characters_present'])}
Emotional beat: {previous_scene['emotional_beat']}
Last action: {previous_scene['action_lines'][-200:] if previous_scene['action_lines'] else ''}...

"""
    
    # Act-specific guidance
    act_guidance = {
        "Act 1": "This is Act 1 — establish the world, characters, and normal life. Pacing can be slower. Build atmosphere.",
        "Act 2A": "This is Act 2A (rising action) — tension increases, conflicts emerge. Scenes can be shorter, cuts faster.",
        "Act 2B": "This is Act 2B (post-midpoint) — stakes are high, pressure building toward climax. Keep scenes tight and punchy.",
        "Act 3": "This is Act 3 (climax and resolution) — lean, intense, fast-paced. Every scene must drive toward conclusion."
    }.get(act_position, "")
    
    # Combined chunks
    novel_text = "\n\n---CHUNK BREAK---\n\n".join(chunks)
    
    prompt = f"""You are an expert screenplay adapter converting a novel into a professional screenplay.

**STORY BIBLE - KEY INFORMATION:**

**Characters (use exact names and descriptions):**
{characters_summary}

**Locations (use exact names):**
{locations_summary}

**Tone:** {story_bible.get('tone', {}).get('mood', 'Unknown')}
**Genre:** {', '.join(story_bible.get('tone', {}).get('genre', []))}
**Period:** {story_bible.get('timeline', {}).get('description', 'Contemporary')}

{prev_scene_info}**CURRENT STORY POSITION:** {scene_context}
**ACT POSITION:** {act_position}
{act_guidance}

---

**NOVEL TEXT TO ADAPT:**

{novel_text}

---

**YOUR TASK:**

Convert the above novel text into 1-4 screenplay scenes in proper Fountain format.

**CRITICAL SCREENPLAY RULES:**

1. **SHOW, DON'T TELL** - Screenplays are VISUAL. If it's an internal thought, you MUST convert it into:
   - Visible facial expression or body language
   - Physical action
   - Dialogue that reveals the thought
   - Or CUT IT if it can't be shown

2. **PRESENT TENSE ONLY** - All action lines in present tense, active voice
   Example: "James walks to the window" NOT "James walked" or "James had walked"

3. **PROPER FOUNTAIN FORMAT:**
   ```
   INT. LOCATION NAME - TIME
   
   Action line describing what we SEE and HEAR.
   
                       CHARACTER NAME
                 (parenthetical if needed)
           Dialogue goes here.
   
   More action.
   ```

4. **CHARACTER NAMES:**
   - Use EXACT names and spellings from Story Bible
   - ALL CAPS in slug lines and when introducing character for first time
   - ALL CAPS for character cues (before dialogue)
   - Once introduced, can use first name in action lines

5. **LOCATION NAMES:**
   - Use exact names from Story Bible
   - INT. (interior), EXT. (exterior), or INT./EXT. (both)
   - Always include TIME OF DAY: DAY, NIGHT, DAWN, DUSK, or CONTINUOUS

6. **WHAT THE CAMERA SEES:**
   - Only describe what can be SEEN or HEARD
   - No abstract concepts, feelings, or backstory exposition
   - Think in shots: Wide shot? Close-up? What's in frame?

7. **DIALOGUE:**
   - Make it NATURAL and speakable
   - Use parentheticals SPARINGLY (only when delivery is ambiguous)
   - Characters can reveal thoughts through subtext, not exposition dumps

8. **ADAPTATION NOTES:**
   - If novel has content that's VERY HARD TO FILM (long flashbacks, complex internal monologue, abstract concepts), include `[  NOTE: ...]` in action lines to flag it

9. **STAY FAITHFUL:**
   - Do NOT invent new plot events
   - Do NOT contradict the Story Bible
   - Keep the story beats from the novel

10. **CONTINUITY:**
    - Respect the previous scene's ending (character locations, time of day, physical state)
    - Time must flow logically: DAY → NIGHT → DAY (not random)
    - Characters cannot teleport between locations

**OUTPUT FORMAT:**

Return ONLY valid Fountain format text. No preamble, no explanations outside the screenplay.

Begin:"""
    
    return prompt


def scene_breakdown_prompt(
    scene: Dict[str, Any],
    story_bible: Dict[str, Any]
) -> str:
    """Generate prompt to extract detailed scene breakdown for video generation.
    
    Args:
        scene: ScreenplayScene dictionary
        story_bible: Complete Story Bible dictionary
    
    Returns:
        LLM prompt string
    """
    # Get character descriptions
    char_descriptions = {}
    for char_name in scene.get('characters_present', []):
        for char in story_bible.get('characters', []):
            if char['name'] == char_name or char_name in char.get('aliases', []):
                char_descriptions[char_name] = char['physical_description']
                break
    
    # Get location description
    location_desc = ""
    for loc in story_bible.get('locations', []):
        if loc['name'] == scene.get('location_name'):
            location_desc = loc['visual_description']
            break
    
    prompt = f"""You are a cinematographer and visual supervisor creating a detailed scene breakdown for VIDEO GENERATION.

**SCENE TO ANALYZE:**

**Scene #{scene['scene_number']}:** {scene['slug_line']}
**Location:** {scene['location_name']}
**Time:** {scene['time_of_day']}
**Emotional Beat:** {scene.get('emotional_beat', 'Unknown')}
**Characters Present:** {', '.join(scene.get('characters_present', []))}

**Action:**
{scene['action_lines']}

**Dialogue:**
{json.dumps(scene.get('dialogue', []), indent=2) if scene.get('dialogue') else 'No dialogue'}

---

**STORY BIBLE REFERENCE:**

**Character Descriptions (use verbatim, no summarizing):**
{json.dumps(char_descriptions, indent=2)}

**Location Description:**
{location_desc}

**Tone:** {story_bible.get('tone', {}).get('mood', 'Unknown')}
**Genre:** {', '.join(story_bible.get('tone', {}).get('genre', []))}
**Period:** {story_bible.get('timeline', {}).get('description', 'Contemporary')}

---

**YOUR TASK:**

Create a comprehensive scene breakdown in JSON format that a video generation AI will use to create this scene.

**Required JSON structure:**

```json
{{
  "emotional_beat": "The key emotional moment/purpose",
  "narrative_purpose": "What this scene accomplishes in the story",
  
  "composition": {{
    "key_moment_description": "Describe the single most important visual moment (the emotional peak)",
    "foreground": "What's in the foreground of the shot",
    "midground": "What's in the midground",
    "background": "What's in the background",
    "lighting": "Cinematographic lighting description (natural/artificial, hard/soft, direction, color temp)",
    "camera_movement": "Suggested camera movement (static, slow push-in, tracking, handheld, etc.)",
    "colour_palette": "Overall color scheme and mood"
  }},
  
  "characters_with_descriptions": {{
    "Character Name": "FULL physical description from Story Bible verbatim - DO NOT SUMMARIZE"
  }},
  
  "location_visual_description": "Full location description from Story Bible verbatim",
  
  "props_and_set_dressing": ["Specific item 1", "Specific item 2", "..."],
  
  "ambient_sound": "Background audio (rain, traffic, wind, silence, etc.)",
  "dialogue_present": true/false,
  "music_mood": "Suggested music mood (tense strings, somber piano, upbeat, silence, etc.)",
  
  "special_requirements": ["Weather effect", "Crowd", "VFX", "Stunt", "etc."],
  "estimated_clip_count": <number of ~10-second video clips needed for this scene>,
  "continuity_notes": "Any visual continuity to maintain (injuries, props, clothing from previous scenes)",
  
  "prompt_ready": true
}}
```

**CRITICAL INSTRUCTIONS:**

1. **BE SPECIFIC** - Phase 3 will use this directly. "Dim lighting" is too vague. "Single practical lamp camera left, warm amber 2700K, hard shadows" is perfect.

2. **INLINE EVERYTHING** - Copy character descriptions and location descriptions VERBATIM from Story Bible into this breakdown. Phase 3 should never need to look up the Story Bible.

3. **THINK CINEMATICALLY:**
   - What lens? Wide? Close-up? Medium?
   - What's the mood? How does lighting support it?
   - What movement tells the story? (static = tense, slow push-in = revelation, handheld = chaos)

4. **PRACTICAL FOR VIDEO AI:**
   - Each ~10s clip should be relatively simple
   - Estimate clip count realistically (dialogue scene with 2 people = 2-4 clips, action sequence = 6-10)
   - Complex shots need to be broken down

5. **AUDIO MATTERS:**
   - Ambient sound creates realism
   - Music mood guides the emotion
   - Note if dialogue is present (affects audio generation)

6. **CONTINUITY FLAGS:**
   - If a character was injured in an earlier scene, note it
   - If they're carrying a specific prop, note it
   - Visual consistency is critical

Return ONLY valid JSON. No preamble, no explanation."""
    
    return prompt


def continuity_check_prompt(
    previous_scene: Dict[str, Any],
    current_scene: Dict[str, Any],
    story_bible: Dict[str, Any]
) -> str:
    """Generate prompt to check continuity between scenes.
    
    Args:
        previous_scene: Previous ScreenplayScene dictionary
        current_scene: Current ScreenplayScene dictionary
        story_bible: Complete Story Bible dictionary
    
    Returns:
        LLM prompt string
    """
    prompt = f"""You are a script supervisor checking continuity between two screenplay scenes.

**PREVIOUS SCENE:**
Scene #{previous_scene['scene_number']}: {previous_scene['slug_line']}
Location: {previous_scene['location_name']}
Time: {previous_scene['time_of_day']}
Characters: {', '.join(previous_scene.get('characters_present', []))}
Last action: {previous_scene['action_lines'][-300:]}

**CURRENT SCENE:**
Scene #{current_scene['scene_number']}: {current_scene['slug_line']}
Location: {current_scene['location_name']}
Time: {current_scene['time_of_day']}
Characters: {', '.join(current_scene.get('characters_present', []))}
First action: {current_scene['action_lines'][:300]}

---

**CHECK FOR CONTINUITY ISSUES:**

1. **Location jumps:** Can characters realistically move from previous location to current location?
2. **Time flow:** Does time of day make sense? (DAY → NIGHT is fine, NIGHT → DAY needs passage of time)
3. **Character state:** If injured/tired/emotional in previous scene, does it carry over?
4. **Props:** Items in hand, clothing changes, must be logical

Return JSON:
```json
{{
  "is_valid": true/false,
  "issues": ["Issue 1", "Issue 2", ...],
  "severity": "minor" | "major" | "none",
  "suggested_fix": "How to resolve if issues found"
}}
```

If continuity is perfect, return {{"is_valid": true, "issues": [], "severity": "none", "suggested_fix": ""}}.

Return ONLY valid JSON."""
    
    return prompt


def act_structure_prompt(
    plot_summary: Dict[str, Any],
    total_chunks: int
) -> str:
    """Generate prompt to determine act structure boundaries.
    
    Args:
        plot_summary: PlotSummary from Story Bible
        total_chunks: Total number of narrative chunks
    
    Returns:
        LLM prompt string
    """
    acts_description = "\n".join([f"{i+1}. {act}" for i, act in enumerate(plot_summary.get('acts', []))])
    
    prompt = f"""You are a story structure expert determining act boundaries for a screenplay adaptation.

**PLOT SUMMARY:**
{plot_summary.get('synopsis', '')}

**ACT BREAKDOWN FROM STORY BIBLE:**
{acts_description if acts_description else "Not provided"}

**TOTAL NARRATIVE CHUNKS:** {total_chunks}

---

**YOUR TASK:**

Determine the chunk ranges for a 4-act structure:
- **Act 1** (Setup): Introduce world, characters, inciting incident (~25% of story)
- **Act 2A** (Rising Action): Conflict emerges, stakes rise (~25%)
- **Act 2B** (Midpoint to Crisis): Post-midpoint complications, darkest hour approaches (~25%)
- **Act 3** (Climax & Resolution): Final confrontation and resolution (~25%)

Return JSON with chunk index ranges (0-indexed):

```json
{{
  "act_one_chunk_range": [0, X],
  "act_two_a_chunk_range": [X+1, Y],
  "act_two_b_chunk_range": [Y+1, Z],
  "act_three_chunk_range": [Z+1, {total_chunks-1}]
}}
```

**EXAMPLE:**
For 320 chunks:
```json
{{
  "act_one_chunk_range": [0, 79],
  "act_two_a_chunk_range": [80, 159],
  "act_two_b_chunk_range": [160, 239],
  "act_three_chunk_range": [240, 319]
}}
```

Use the Story Bible acts as guidance, but adjust for standard screenplay structure. Return ONLY valid JSON."""
    
    return prompt
