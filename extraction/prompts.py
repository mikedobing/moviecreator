"""LLM prompt templates for Story Bible extraction."""
from typing import List


def character_extraction_prompt(chunks: List[str]) -> str:
    """Generate prompt for character extraction.
    
    Args:
        chunks: List of narrative text chunks
        
    Returns:
        Formatted prompt string
    """
    text = "\n\n---\n\n".join(chunks)
    
    return f"""You are analyzing narrative text to extract detailed character information for video generation purposes.

Please carefully read the following text and extract ALL characters mentioned. For each character, provide:

1. **Name**: Full name or primary identifier
2. **Aliases**: Any nicknames, titles, or alternative names used
3. **Role**: Categorize as "protagonist", "antagonist", "supporting", or "minor"
4. **Physical Description**: CRITICALLY IMPORTANT - Describe in cinematic detail:
   - Hair color, style, length
   - Eye color
   - Height and build
   - Distinctive features (scars, tattoos, etc.)
   - Typical clothing style
   - Age or age range
   - Skin tone
   Any visual details that would help generate a consistent video character
5. **Personality**: Core personality traits and mannerisms
6. **Backstory Summary**: Brief background (2-3 sentences)
7. **Relationships**: Key relationships with other characters
8. **Notable Quotes**: 1-3 memorable quotes if available

Focus heavily on PHYSICAL APPEARANCE - these descriptions will be used to generate video prompts. Be as specific and detailed as possible about how characters look.

Return the result as a JSON array of character objects matching this structure:
```json
[
  {{
    "name": "Character Name",
    "aliases": ["Nickname1", "Title"],
    "role": "protagonist",
    "physical_description": "Detailed visual description...",
    "personality": "Personality traits...",
    "backstory_summary": "Brief background...",
    "relationships": {{"Character2": "friend", "Character3": "rival"}},
    "first_appearance_chunk": "",
    "notable_quotes": ["Quote 1", "Quote 2"]
  }}
]
```

TEXT TO ANALYZE:

{text}

Return ONLY the JSON array, no additional text."""


def location_extraction_prompt(chunks: List[str]) -> str:
    """Generate prompt for location extraction.
    
    Args:
        chunks: List of narrative text chunks
        
    Returns:
        Formatted prompt string
    """
    text = "\n\n---\n\n".join(chunks)
    
    return f"""You are analyzing narrative text to extract detailed location information for video generation purposes.

Please read the following text and extract ALL significant locations. For each location, provide:

1. **Name**: Location name or identifier
2. **Location Type**: Categorize (interior, exterior, urban, rural, fantasy, etc.)
3. **Visual Description**: CRITICALLY IMPORTANT - Describe as a cinematographer would:
   - Lighting (natural/artificial, bright/dim, color temperature)
   - Spatial layout (depth, scale, dimensions)
   - Color palette and textures
   - Key visual elements and details
   - Architecture or landscape features
4. **Atmosphere**: Mood, feeling, emotional tone of the space
5. **Associated Characters**: Which characters frequently appear here
6. **Significance**: Role in the story

Think in terms of how this location would appear on screen. These descriptions will generate video backdrops.

Return the result as a JSON array matching this structure:
```json
[
  {{
    "name": "Location Name",
    "location_type": "interior",
    "visual_description": "Detailed cinematographic description...",
    "atmosphere": "Mood and feeling...",
    "associated_characters": ["Character1", "Character2"],
    "significance": "Plot role..."
  }}
]
```

TEXT TO ANALYZE:

{text}

Return ONLY the JSON array, no additional text."""


def tone_extraction_prompt(chunks: List[str]) -> str:
    """Generate prompt for narrative tone extraction.
    
    Args:
        chunks: List of narrative text chunks
        
    Returns:
        Formatted prompt string
    """
    text = "\n\n---\n\n".join(chunks)
    
    return f"""You are analyzing narrative text to determine its overall tone and style for video adaptation.

Read the following text and determine:

1. **Genre**: List all applicable genres
2. **Mood**: Overall emotional register
3. **Pacing**: Describe the story's rhythm (fast-paced, slow-burn, episodic, etc.)
4. **Style Notes**: IMPORTANT - Think in terms of comparable FILMS, not books:
   - Visual style (gritty/polished, saturated/desaturated, etc.)
   - Camera style (handheld/steady, wide shots/close-ups, etc.)
   - Reference comparable films if helpful
5. **Violence Level**: none, mild, moderate, graphic
6. **Content Warnings**: Any sensitive content to note

Return the result as a JSON object matching this structure:
```json
{{
  "genre": ["genre1", "genre2"],
  "mood": "Overall mood...",
  "pacing": "Pacing description...",
  "style_notes": "Visual and cinematic style...",
  "violence_level": "moderate",
  "content_warnings": ["warning1", "warning2"]
}}
```

TEXT TO ANALYZE:

{text}

Return ONLY the JSON object, no additional text."""


def plot_summary_prompt(chunks: List[str]) -> str:
    """Generate prompt for plot summary extraction.
    
    Args:
        chunks: List of narrative text chunks
        
    Returns:
        Formatted prompt string
    """
    text = "\n\n---\n\n".join(chunks)
    
    return f"""You are summarizing a narrative for adaptation into video format.

Read the following text and provide:

1. **Logline**: One sentence summary of the core story
2. **Synopsis**: 200-word overview of the plot
3. **Acts**: Three-act breakdown (beginning, middle, end)
4. **Key Themes**: Main thematic elements

Return the result as a JSON object matching this structure:
```json
{{
  "logline": "One sentence story summary...",
  "synopsis": "200-word plot overview...",
  "acts": [
    "Act 1: Beginning...",
    "Act 2: Middle...",
    "Act 3: End..."
  ],
  "key_themes": ["theme1", "theme2", "theme3"]
}}
```

TEXT TO ANALYZE:

{text}

Return ONLY the JSON object, no additional text."""


def world_rules_prompt(chunks: List[str]) -> str:
    """Generate prompt for world rules extraction.
    
    Args:
        chunks: List of narrative text chunks
        
    Returns:
        Formatted prompt string
    """
    text = "\n\n---\n\n".join(chunks)
    
    return f"""You are analyzing a narrative to extract any special rules governing its world.

This might include:
- Magic systems and their limitations
- Technology constraints or capabilities
- Physical laws that differ from reality
- Social rules or hierarchy systems
- Special abilities or powers

Read the following text and extract any world-building rules that are important for maintaining consistency in video generation.

If this is a realistic fiction with no special rules, return an empty array.

Return the result as a JSON array of strings:
```json
["Rule 1: Description...", "Rule 2: Description...", "Rule 3: Description..."]
```

TEXT TO ANALYZE:

{text}

Return ONLY the JSON array, no additional text."""


def merge_character_profiles_prompt(profiles: List[dict]) -> str:
    """Generate prompt for merging duplicate character profiles.
    
    Args:
        profiles: List of character profile dictionaries
        
    Returns:
        Formatted prompt string
    """
    import json
    profiles_json = json.dumps(profiles, indent=2)
    
    return f"""You are consolidating character information from multiple extraction passes.

You have extracted character profiles from different sections of a novel. Some characters may appear multiple times with slight variations in name or description. Your task is to:

1. **Identify duplicates**: Same character referred to differently (e.g., "James", "Jim", "Mr. Harrison")
2. **Merge duplicates**: Combine information, using the most detailed descriptions
3. **Resolve conflicts**: If descriptions conflict, use the most common or detailed version
4. **Preserve unique characters**: Don't merge truly different characters

PROFILES TO MERGE:

{profiles_json}

Return a consolidated JSON array of unique character profiles using the same structure:
```json
[
  {{
    "name": "Primary Name",
    "aliases": ["all", "known", "aliases"],
    "role": "protagonist",
    "physical_description": "Most complete description...",
    "personality": "Merged personality traits...",
    "backstory_summary": "Combined backstory...",
    "relationships": {{"Character": "relationship"}},
    "first_appearance_chunk": "",
    "notable_quotes": ["quote1", "quote2"]
  }}
]
```

Return ONLY the JSON array, no additional text."""
