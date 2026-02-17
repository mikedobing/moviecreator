"""Test Pydantic models."""
import pytest
from extraction.models import CharacterProfile, Location, StoryBible, TimelinePeriod, NarrativeTone, PlotSummary


def test_character_profile_creation():
    """Test creating a character profile."""
    char = CharacterProfile(
        name="John Doe",
        aliases=["Johnny"],
        role="protagonist",
        physical_description="Tall with dark hair",
        personality="Brave and determined",
        backstory_summary="A detective with a troubled past",
        relationships={"Jane": "partner"},
        first_appearance_chunk="chunk-1",
        notable_quotes=["I'll find the truth"]
    )
    
    assert char.name == "John Doe"
    assert len(char.aliases) == 1
    assert char.role == "protagonist"


def test_story_bible_creation():
    """Test creating a complete Story Bible."""
    timeline = TimelinePeriod(
        description="Modern day",
        era="Contemporary",
        technology_level="Current",
        cultural_notes="Urban setting"
    )
    
    tone = NarrativeTone(
        genre=["thriller"],
        mood="tense",
        pacing="fast-paced",
        style_notes="Gritty, handheld camera feel",
        violence_level="moderate",
        content_warnings=[]
    )
    
    plot = PlotSummary(
        logline="A detective hunts a serial killer",
        synopsis="A gripping tale of...",
        acts=["Act 1", "Act 2", "Act 3"],
        key_themes=["justice", "redemption"]
    )
    
    bible = StoryBible(
        novel_title="Test Novel",
        characters=[],
        locations=[],
        timeline=timeline,
        tone=tone,
        plot=plot,
        world_rules=[],
        visual_style_notes="Dark and moody"
    )
    
    assert bible.novel_title == "Test Novel"
    assert bible.tone.genre == ["thriller"]
    assert len(bible.plot.acts) == 3


def test_location_validation():
    """Test location model."""
    loc = Location(
        name="Detective's Office",
        location_type="interior",
        visual_description="Cluttered desk, dim lighting",
        atmosphere="Noir-ish",
        associated_characters=["John Doe"],
        significance="Main workspace"
    )
    
    assert loc.name == "Detective's Office"
    assert loc.location_type == "interior"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
