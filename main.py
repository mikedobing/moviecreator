"""Main CLI entry point for Novel Pipeline."""
import click
import hashlib
import json
from pathlib import Path
from anthropic import Anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from utils.logger import setup_logger
from storage.database import Database
from storage.vector_store import VectorStore
from ingestion.pdf_extractor import PDFExtractor, PDFExtractionError
from ingestion.chunker import NarrativeChunker
from extraction.story_bible_extractor import StoryBibleExtractor
import config

logger = setup_logger(__name__)
console = Console()


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        Hex digest of hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


@click.group()
def cli():
    """Novel-to-Screen Pipeline - Phase 1: Novel Ingestion & Story Bible Extraction"""
    pass


@cli.command()
@click.option('--pdf', required=True, type=click.Path(exists=True), help='Path to PDF novel')
def ingest(pdf):
    """Ingest a PDF novel and create chunks."""
    console.print("\n[bold cyan]Novel Ingestion[/bold cyan]\n")
    
    pdf_path = Path(pdf)
    
    # Initialize components
    db = Database()
    vector_store = VectorStore()
    extractor = PDFExtractor()
    chunker = NarrativeChunker()
    
    # Compute file hash
    console.print("Computing file hash...")
    file_hash = compute_file_hash(pdf_path)
    
    # Check if already processed
    existing_novel = db.get_novel_by_hash(file_hash)
    if existing_novel:
        console.print(f"[yellow]Novel already ingested: {existing_novel['title']} (ID: {existing_novel['id']})[/yellow]")
        return
    
    # Extract PDF
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Extracting PDF text...", total=None)
        
        try:
            doc = extractor.extract(str(pdf_path))
            progress.update(task, completed=True)
        except PDFExtractionError as e:
            console.print(f"[red]Error: {e}[/red]")
            return
    
    # Insert novel into database
    novel_id = db.insert_novel(
        title=doc.title,
        file_path=str(pdf_path.absolute()),
        file_hash=file_hash,
        page_count=doc.page_count,
        word_count=doc.metadata.get('word_count', 0)
    )
    
    # Chunk text
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Chunking narrative...", total=None)
        chunks = chunker.chunk(doc)
        progress.update(task, completed=True)
    
    # Store chunks in database
    console.print("Storing chunks in database...")
    chunk_dicts = []
    for chunk in chunks:
        chunk_dict = chunk.to_dict()
        chunk_dict['novel_id'] = novel_id
        chunk_dicts.append(chunk_dict)
    
    db.insert_chunks(chunk_dicts)
    
    # Store chunks in vector store
    console.print("Generating embeddings and storing in vector database...")
    vector_store.add_chunks(chunk_dicts, novel_id)
    
    console.print(f"\n[green]✓ Ingestion complete![/green]")
    console.print(f"Novel ID: [cyan]{novel_id}[/cyan]")
    console.print(f"Title: [cyan]{doc.title}[/cyan]")
    console.print(f"Pages: {doc.page_count}")
    console.print(f"Chunks: {len(chunks)}")


@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
def extract_bible(novel_id):
    """Extract Story Bible from an ingested novel."""
    console.print("\n[bold cyan]Story Bible Extraction[/bold cyan]\n")
    
    # Check API key
    if not config.ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY not set in environment[/red]")
        return
    
    # Initialize components
    db = Database()
    
    # Get chunks
    console.print(f"Loading chunks for novel [cyan]{novel_id}[/cyan]...")
    chunk_dicts = db.get_chunks(novel_id)
    
    if not chunk_dicts:
        console.print("[red]Error: No chunks found for this novel ID[/red]")
        return
    
    # Convert to NarrativeChunk objects
    from ingestion.models import NarrativeChunk
    chunks = [
        NarrativeChunk(
            chunk_id=c['id'],
            novel_title=c.get('novel_title', ''),
            chapter_number=c['chapter_number'],
            chunk_index=c['chunk_index'],
            text=c['text'],
            token_count=c['token_count'],
            start_char=c['start_char'],
            end_char=c['end_char']
        )
        for c in chunk_dicts
    ]
    
    novel_title = chunks[0].novel_title if chunks else "Unknown"
    
    console.print(f"Found {len(chunks)} chunks")
    console.print(f"Initializing LLM extractor with model: [cyan]{config.ANTHROPIC_MODEL}[/cyan]\n")
    
    # Initialize extractor
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    extractor = StoryBibleExtractor(client, config.ANTHROPIC_MODEL)
    
    # Extract Story Bible
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Extracting Story Bible (this may take several minutes)...", total=None)
        
        try:
            story_bible = extractor.extract(chunks, novel_title, novel_id=novel_id)
            progress.update(task, completed=True)
        except Exception as e:
            console.print(f"[red]Error during extraction: {e}[/red]")
            logger.exception("Extraction failed")
            return
    
    # Save to database
    console.print("Saving Story Bible to database...")
    bible_dict = story_bible.model_dump()
    db.insert_story_bible(novel_id, bible_dict, config.ANTHROPIC_MODEL)
    
    # Export to JSON file
    output_path = config.STORY_BIBLES_DIR / f"{novel_title}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(bible_dict, f, indent=2, ensure_ascii=False)
    
    console.print(f"\n[green]✓ Story Bible extraction complete![/green]")
    console.print(f"Characters: {len(story_bible.characters)}")
    console.print(f"Locations: {len(story_bible.locations)}")
    console.print(f"Tokens used: {extractor.total_tokens_used:,}")
    console.print(f"Exported to: [cyan]{output_path}[/cyan]")


@cli.command()
@click.option('--pdf', required=True, type=click.Path(exists=True), help='Path to PDF novel')
def run_all(pdf):
    """Run complete pipeline: ingest + extract Story Bible."""
    console.print("\n[bold cyan]Novel-to-Screen Pipeline - Full Run[/bold cyan]\n")
    
    pdf_path = Path(pdf)
    
    # Check API key
    if not config.ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY not set in environment[/red]")
        return
    
    # Step 1: Ingest
    console.print("[bold]Step 1: Ingesting PDF[/bold]\n")
    
    db = Database()
    vector_store = VectorStore()
    extractor = PDFExtractor()
    chunker = NarrativeChunker()
    
    # Compute file hash
    file_hash = compute_file_hash(pdf_path)
    
    # Check if already processed
    existing_novel = db.get_novel_by_hash(file_hash)
    if existing_novel:
        console.print(f"[yellow]Novel already ingested, skipping ingestion[/yellow]")
        novel_id = existing_novel['id']
        novel_title = existing_novel['title']
    else:
        # Extract and chunk
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task1 = progress.add_task("Extracting PDF...", total=None)
            try:
                doc = extractor.extract(str(pdf_path))
                progress.update(task1, completed=True)
            except PDFExtractionError as e:
                console.print(f"[red]Error: {e}[/red]")
                return
            
            task2 = progress.add_task("Chunking...", total=None)
            chunks = chunker.chunk(doc)
            progress.update(task2, completed=True)
        
        # Store in database
        novel_id = db.insert_novel(
            title=doc.title,
            file_path=str(pdf_path.absolute()),
            file_hash=file_hash,
            page_count=doc.page_count,
            word_count=doc.metadata.get('word_count', 0)
        )
        
        chunk_dicts = []
        for chunk in chunks:
            chunk_dict = chunk.to_dict()
            chunk_dict['novel_id'] = novel_id
            chunk_dicts.append(chunk_dict)
        
        db.insert_chunks(chunk_dicts)
        
        console.print("Storing in vector database...")
        vector_store.add_chunks(chunk_dicts, novel_id)
        
        novel_title = doc.title
        console.print(f"[green]✓ Ingestion complete ({len(chunks)} chunks)[/green]\n")
    
    # Step 2: Extract Story Bible
    console.print("[bold]Step 2: Extracting Story Bible[/bold]\n")
    
    # Get chunks
    chunk_dicts = db.get_chunks(novel_id)
    from ingestion.models import NarrativeChunk
    chunks = [
        NarrativeChunk(
            chunk_id=c['id'],
            novel_title=novel_title,
            chapter_number=c['chapter_number'],
            chunk_index=c['chunk_index'],
            text=c['text'],
            token_count=c['token_count'],
            start_char=c['start_char'],
            end_char=c['end_char']
        )
        for c in chunk_dicts
    ]
    
    # Extract
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    bible_extractor = StoryBibleExtractor(client, config.ANTHROPIC_MODEL)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Extracting Story Bible...", total=None)
        story_bible = bible_extractor.extract(chunks, novel_title, novel_id=novel_id)
        progress.update(task, completed=True)
    
    # Save
    bible_dict = story_bible.model_dump()
    db.insert_story_bible(novel_id, bible_dict, config.ANTHROPIC_MODEL)
    
    output_path = config.STORY_BIBLES_DIR / f"{novel_title}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(bible_dict, f, indent=2, ensure_ascii=False)
    
    # Summary
    console.print("\n[bold green]✓ Pipeline Complete![/bold green]\n")
    
    table = Table(show_header=False)
    table.add_row("Novel ID", f"[cyan]{novel_id}[/cyan]")
    table.add_row("Title", novel_title)
    table.add_row("Characters", str(len(story_bible.characters)))
    table.add_row("Locations", str(len(story_bible.locations)))
    table.add_row("Tokens Used", f"{bible_extractor.total_tokens_used:,}")
    table.add_row("Output File", str(output_path))
    
    console.print(table)


@cli.command()
def status():
    """Show all processed novels."""
    db = Database()
    novels = db.get_all_novels()
    
    if not novels:
        console.print("[yellow]No novels have been processed yet[/yellow]")
        return
    
    table = Table(title="Processed Novels")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Pages", justify="right")
    table.add_column("Words", justify="right")
    table.add_column("Ingested", style="dim")
    
    for novel in novels:
        table.add_row(
            novel['id'][:8] + "...",
            novel['title'],
            str(novel['page_count']),
            f"{novel['word_count']:,}",
            novel['ingested_at'][:10]
        )
    
    console.print(table)


@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
@click.option('--output', required=True, type=click.Path(), help='Output JSON path')
def export_bible(novel_id, output):
    """Export Story Bible to JSON file."""
    db = Database()
    
    story_bible = db.get_story_bible(novel_id)
    
    if not story_bible:
        console.print("[red]Error: No Story Bible found for this novel ID[/red]")
        return
    
    output_path = Path(output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(story_bible, f, indent=2, ensure_ascii=False)
    
    console.print(f"[green]✓ Story Bible exported to {output_path}[/green]")


# ==================== Phase 2 Commands ====================

@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
def phase2(novel_id):
    """Run Phase 2: Convert screenplay + generate scene breakdowns."""
    console.print("\n[bold cyan]Phase 2: Screenplay Conversion + Scene Breakdown[/bold cyan]\n")
    
    # Check API key
    if not config.ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY not set in environment[/red]")
        return
    
    from screenplay.converter import ScreenplayConverter
    from screenplay.formatter import FountainFormatter
    from screenplay.scene_breakdown import SceneBreakdownExtractor
    from extraction.models import StoryBible
    
    db = Database()
    vector_store = VectorStore()
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    # Get novel info
    novels = db.get_all_novels()
    novel = next((n for n in novels if n['id'] == novel_id), None)
    if not novel:
        console.print(f"[red]Error: Novel {novel_id} not found[/red]")
        return
    
    novel_title = novel['title']
    console.print(f"Processing: [cyan]{novel_title}[/cyan]\n")
    
    # Step 1: Convert to screenplay
    console.print("[bold]Step 1: Converting to Screenplay[/bold]\n")
    
    converter = ScreenplayConverter(client, db, vector_store, config.ANTHROPIC_MODEL)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Converting novel to screenplay...", total=None)
        
        try:
            screenplay = converter.convert(novel_id, use_checkpoints=True)
            progress.update(task, completed=True)
        except Exception as e:
            console.print(f"[red]Error during conversion: {e}[/red]")
            logger.exception("Conversion failed")
            return
    
    console.print(f"[green]✓ Created {screenplay.scene_count} scenes (~{screenplay.page_count_estimate} pages)[/green]\n")
    
    # Step 2: Format and export screenplay
    console.print("[bold]Step 2: Formatting Screenplay[/bold]\n")
    
    formatter = FountainFormatter()
    screenplay.fountain_text = formatter.format(screenplay)
    
    # Export files
    screenplay_dir = config.OUTPUT_DIR / "screenplays"
    screenplay_dir.mkdir(parents=True, exist_ok=True)
    
    fountain_path = screenplay_dir / f"{novel_title}.fountain"
    json_path = screenplay_dir / f"{novel_title}_screenplay.json"
    
    formatter.export_fountain_file(screenplay, str(fountain_path))
    formatter.export_json(screenplay, str(json_path))
    
    console.print(f"[green]✓ Exported screenplay[/green]")
    console.print(f"  Fountain: {fountain_path}")
    console.print(f"  JSON: {json_path}\n")
    
    # Step 3: Generate scene breakdowns
    console.print("[bold]Step 3: Generating Scene Breakdowns[/bold]\n")
    
    # Load Story Bible
    story_bible_dict = db.get_story_bible(novel_id)
    story_bible = StoryBible(**story_bible_dict)
    
    breakdown_extractor = SceneBreakdownExtractor(client, db, config.ANTHROPIC_MODEL)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Processing {len(screenplay.scenes)} scenes...", total=None)
        
        try:
            breakdowns = breakdown_extractor.process_all_scenes(screenplay.scenes, story_bible)
            progress.update(task, completed=True)
        except Exception as e:
            console.print(f"[red]Error during breakdown: {e}[/red]")
            logger.exception("Breakdown failed")
            return
    
    # Export scene breakdowns
    breakdown_dir = config.OUTPUT_DIR / "scene_breakdowns"
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    
    breakdown_path = breakdown_dir / f"{novel_title}_breakdown.json"
    with open(breakdown_path, 'w', encoding='utf-8') as f:
        json.dump([b.model_dump() for b in breakdowns], f, indent=2, ensure_ascii=False)
    
    console.print(f"[green]✓ Exported scene breakdowns to {breakdown_path}[/green]\n")
    
    # Summary
    console.print("[bold green]✓ Phase 2 Complete![/bold green]\n")
    
    table = Table(show_header=False)
    table.add_row("Novel", novel_title)
    table.add_row("Scenes", str(screenplay.scene_count))
    table.add_row("Estimated Pages", str(screenplay.page_count_estimate))
    table.add_row("Tokens Used", f"{converter.total_tokens_used + breakdown_extractor.total_tokens_used:,}")
    table.add_row("Screenplay", str(fountain_path))
    table.add_row("Breakdowns", str(breakdown_path))
    
    console.print(table)


@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
def convert_script(novel_id):
    """Convert novel to screenplay (Phase 2 Step 1 only)."""
    console.print("\n[bold cyan]Screenplay Conversion[/bold cyan]\n")
    
    if not config.ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        return
    
    from screenplay.converter import ScreenplayConverter
    from screenplay.formatter import FountainFormatter
    
    db = Database()
    vector_store = VectorStore()
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    converter = ScreenplayConverter(client, db, vector_store, config.ANTHROPIC_MODEL)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Converting...", total=None)
        screenplay = converter.convert(novel_id)
        progress.update(task, completed=True)
    
    # Format and export
    formatter = FountainFormatter()
    screenplay.fountain_text = formatter.format(screenplay)
    
    screenplay_dir = config.OUTPUT_DIR / "screenplays"
    screenplay_dir.mkdir(parents=True, exist_ok=True)
    
    novel_title = screenplay.novel_title
    fountain_path = screenplay_dir / f"{novel_title}.fountain"
    json_path = screenplay_dir / f"{novel_title}_screenplay.json"
    
    formatter.export_fountain_file(screenplay, str(fountain_path))
    formatter.export_json(screenplay, str(json_path))
    
    console.print(f"\n[green]✓ Screenplay created: {screenplay.scene_count} scenes[/green]")
    console.print(f"Exported to: {fountain_path}")


@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
def breakdown_scenes(novel_id):
    """Generate scene breakdowns from screenplay (Phase 2 Step 2 only)."""
    console.print("\n[bold cyan]Scene Breakdown Generation[/bold cyan]\n")
    
    if not config.ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        return
    
    from screenplay.scene_breakdown import SceneBreakdownExtractor
    from extraction.models import StoryBible
    
    db = Database()
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    # Load screenplay from JSON
    novels = db.get_all_novels()
    novel = next((n for n in novels if n['id'] == novel_id), None)
    if not novel:
        console.print(f"[red]Error: Novel not found[/red]")
        return
    
    novel_title = novel['title']
    screenplay_path = config.OUTPUT_DIR / "screenplays" / f"{novel_title}_screenplay.json"
    
    if not screenplay_path.exists():
        console.print(f"[red]Error: Screenplay not found. Run convert-script first.[/red]")
        return
    
    with open(screenplay_path, 'r') as f:
        from extraction.models import Screenplay
        screenplay = Screenplay(**json.load(f))
    
    # Load Story Bible
    story_bible_dict = db.get_story_bible(novel_id)
    story_bible = StoryBible(**story_bible_dict)
    
    # Generate breakdowns
    extractor = SceneBreakdownExtractor(client, db, config.ANTHROPIC_MODEL)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Processing {len(screenplay.scenes)} scenes...", total=None)
        breakdowns = extractor.process_all_scenes(screenplay.scenes, story_bible)
        progress.update(task, completed=True)
    
    # Export
    breakdown_dir = config.OUTPUT_DIR / "scene_breakdowns"
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    
    breakdown_path = breakdown_dir / f"{novel_title}_breakdown.json"
    with open(breakdown_path, 'w', encoding='utf-8') as f:
        json.dump([b.model_dump() for b in breakdowns], f, indent=2, ensure_ascii=False)
    
    console.print(f"\n[green]✓ Generated {len(breakdowns)} scene breakdowns[/green]")
    console.print(f"Exported to: {breakdown_path}")


@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
def list_scenes(novel_id):
    """List all scenes in a screenplay."""
    from extraction.models import Screenplay
    
    db = Database()
    novels = db.get_all_novels()
    novel = next((n for n in novels if n['id'] == novel_id), None)
    
    if not novel:
        console.print("[red]Error: Novel not found[/red]")
        return
    
    novel_title = novel['title']
    screenplay_path = config.OUTPUT_DIR / "screenplays" / f"{novel_title}_screenplay.json"
    
    if not screenplay_path.exists():
        console.print("[red]Error: Screenplay not found. Run convert-script first.[/red]")
        return
    
    with open(screenplay_path, 'r') as f:
        screenplay = Screenplay(**json.load(f))
    
    table = Table(title=f"Scenes - {novel_title}")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Slug Line")
    table.add_column("Type")
    table.add_column("Characters", style="dim")
    
    for scene in screenplay.scenes:
        table.add_row(
            str(scene.scene_number),
            scene.slug_line,
            scene.scene_type,
            ", ".join(scene.characters_present[:3]) + ("..." if len(scene.characters_present) > 3 else "")
        )
    
    console.print(table)
    console.print(f"\nTotal: {len(screenplay.scenes)} scenes, ~{screenplay.page_count_estimate} pages")


# ==================== Phase 3 Commands ====================

@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
@click.option('--api', default='seedance', help='API provider: seedance, kling, or runwayml')
def phase3(novel_id: str, api: str):
    """Run Phase 3: Generate video prompts + build job queue."""
    from prompts.video_prompt_engineer import VideoPromptEngineer
    from prompts.validators import PromptValidator
    from generation.job_queue import JobQueue
    from generation.cost_estimator import CostEstimator

    console.print("[bold cyan]Phase 3: Video Prompt Engineering & Generation Orchestration[/bold cyan]\n")

    db = Database()

    # Load Phase 1 Story Bible
    story_bible_data = db.get_story_bible(novel_id)
    if not story_bible_data:
        console.print("[red]Error: Story Bible not found. Run Phase 1 first.[/red]")
        return

    # Load Phase 2 scene breakdowns
    breakdown_path = None
    output_dir = Path(config.OUTPUT_DIR) / "scene_breakdowns"
    if output_dir.exists():
        for f in output_dir.glob("*_breakdown.json"):
            breakdown_path = f
            break
    
    if not breakdown_path or not breakdown_path.exists():
        console.print("[red]Error: Scene breakdowns not found. Run Phase 2 first.[/red]")
        return

    console.print(f"Loading breakdown from: {breakdown_path}")
    try:
        with open(breakdown_path, 'r') as f:
            breakdowns = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON Error in {breakdown_path}: {e}[/red]")
        with open(breakdown_path, 'r') as f:
            console.print(f"First 100 bytes: {f.read(100)}")
        return

    console.print(f"[green]✓ Loaded {len(breakdowns)} scene breakdowns[/green]")

    # --- Step 1: Generate prompts ---
    console.print("\n[bold green]Step 1: Generating video prompts...[/bold green]")
    engineer = VideoPromptEngineer(story_bible_data)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task(f"Processing {len(breakdowns)} scenes...", total=len(breakdowns))
        all_prompts = []
        for breakdown in breakdowns:
            scene_prompts = engineer.generate_prompts_for_scene(breakdown, novel_id)
            all_prompts.extend(scene_prompts)
            progress.advance(task)

    console.print(f"[green]✓ Generated {len(all_prompts)} video prompts from {len(breakdowns)} scenes[/green]")

    # --- Step 2: Validate prompts ---
    console.print("\n[bold green]Step 2: Validating prompts...[/bold green]")
    validation = PromptValidator.validate_all(all_prompts)

    if validation["all_valid"]:
        console.print(f"[green]✓ All {validation['total_prompts']} prompts valid[/green]")
    else:
        console.print(f"[yellow]⚠ {validation['total_errors']} errors, {validation['total_warnings']} warnings[/yellow]")

    if validation["total_warnings"] > 0:
        console.print(f"[dim]  Warnings: {validation['total_warnings']}[/dim]")

    # Temporal coherence
    temporal = validation["temporal_report"]
    if temporal.is_coherent:
        console.print("[green]✓ Temporal coherence check passed[/green]")
    else:
        for issue in temporal.issues:
            console.print(f"[yellow]  ⚠ {issue}[/yellow]")

    # Character consistency
    consistency = validation["consistency_reports"]
    inconsistent = [r for r in consistency if not r.consistent_descriptions]
    if not inconsistent:
        console.print(f"[green]✓ Character consistency check passed ({len(consistency)} characters)[/green]")
    else:
        for r in inconsistent:
            console.print(f"[yellow]  ⚠ {r.character_name}: {', '.join(r.discrepancies)}[/yellow]")

    # --- Step 3: Save prompts to database ---
    console.print("\n[bold green]Step 3: Saving prompts to database...[/bold green]")
    with db._get_connection() as conn:
        for prompt in all_prompts:
            conn.execute(
                """INSERT OR REPLACE INTO video_prompts
                   (id, scene_id, novel_id, clip_index, prompt_type, prompt_text,
                    negative_prompt, duration_seconds, aspect_ratio, motion_intensity,
                    camera_movement, reference_image_path, character_consistency_tags,
                    audio_prompt, generation_params, estimated_cost_usd, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (prompt.prompt_id, prompt.scene_id, prompt.novel_id, prompt.clip_index,
                 prompt.prompt_type, prompt.prompt_text, prompt.negative_prompt,
                 prompt.duration_seconds, prompt.aspect_ratio, prompt.motion_intensity,
                 prompt.camera_movement, prompt.reference_image_path,
                 json.dumps(prompt.character_consistency_tags),
                 prompt.audio_prompt, json.dumps(prompt.generation_params),
                 prompt.estimated_cost_usd, prompt.created_at)
            )
        conn.commit()
    console.print(f"[green]✓ Saved {len(all_prompts)} prompts to database[/green]")

    # --- Step 4: Build job queue ---
    console.print("\n[bold green]Step 4: Building job queue...[/bold green]")
    job_queue = JobQueue(db)
    jobs = job_queue.add_jobs_from_prompts(all_prompts, api_provider=api)
    console.print(f"[green]✓ Created {len(jobs)} generation jobs for {api}[/green]")

    # --- Step 5: Cost estimation ---
    console.print("\n[bold green]Step 5: Cost estimation...[/bold green]")
    estimator = CostEstimator(api_provider=api)
    cost = estimator.estimate_novel_cost(all_prompts)

    console.print(f"  Total clips: [cyan]{cost.total_clips}[/cyan]")
    console.print(f"  Total video duration: [cyan]{cost.total_duration_minutes} minutes[/cyan]")
    console.print(f"  Estimated cost ({api}): [cyan]${cost.estimated_cost_usd:.2f} USD[/cyan]")

    # Compare providers
    comparison = estimator.compare_providers(all_prompts)
    console.print("\n  Provider cost comparison:")
    for provider, prov_cost in comparison.items():
        marker = " ← selected" if provider == api else ""
        console.print(f"    {provider}: ${prov_cost:.2f}{marker}")

    # --- Step 6: Export outputs ---
    console.print("\n[bold green]Step 6: Exporting outputs...[/bold green]")

    # Export prompts JSON
    prompts_dir = Path(config.OUTPUT_DIR) / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine title for filenames
    title = story_bible_data.get("novel_title", "novel").lower().replace(" ", "_")
    prompts_path = prompts_dir / f"{title}_prompts.json"
    
    prompts_data = [p.model_dump() for p in all_prompts]
    with open(prompts_path, 'w') as f:
        json.dump(prompts_data, f, indent=2)
    console.print(f"[green]✓ Exported prompts to {prompts_path}[/green]")


# ==================== Phase 4 Commands ====================

@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
@click.option('--max-concurrent', default=5, help='Max concurrent jobs')
@click.option('--resume', is_flag=True, default=True, help='Resume from last state')
def execute_queue(novel_id, max_concurrent, resume):
    """Run video generation job queue (Phase 4)."""
    import asyncio
    from execution.job_executor import JobExecutor
    from execution.api_clients import SeedanceClient, RateLimits
    from monitoring.progress_tracker import ProgressTracker
    
    console.print("[bold cyan]Phase 4: Video Generation Execution[/bold cyan]\n")
    
    db = Database()
    
    # Initialize components
    # In production, we would load API key from env/config
    api_key = "test_key" 
    console.print("[yellow]Note: Using placeholder API key and client[/yellow]")
    
    client = SeedanceClient(api_key=api_key, base_url="https://api.example.com")
    executor = JobExecutor(db, client=client)
    
    # Run execution
    console.print(f"Starting execution for novel [cyan]{novel_id}[/cyan]...")
    console.print(f"Max concurrent jobs: {max_concurrent}")
    console.print(f"Resume mode: {resume}")
    
    try:
        # Since we are in a synchronous CLI command, we need to run async code
        report = asyncio.run(executor.execute_queue(
            novel_id=novel_id,
            max_concurrent_jobs=max_concurrent,
            resume=resume
        ))
        
        console.print("\n[bold green]✓ Execution Complete![/bold green]\n")
        table = Table(show_header=False)
        table.add_row("Total Jobs", str(report.total_jobs))
        table.add_row("Completed", f"[green]{report.completed}[/green]")
        table.add_row("Failed", f"[red]{report.failed}[/red]")
        table.add_row("Skipped", f"[yellow]{report.skipped}[/yellow]")
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error during execution: {e}[/red]")
        logger.exception("Execution failed")


@cli.command()
@click.option('--scene-id', required=True, help='Scene UUID')
@click.option('--output', required=True, help='Output MP4 path')
def assemble_scene(scene_id, output):
    """Assemble clips for a single scene."""
    from assembly.clip_assembler import ClipAssembler
    import glob
    
    console.print("[bold cyan]Scene Assembly[/bold cyan]\n")
    
    assembler = ClipAssembler()
    
    # Find clips for this scene
    # This assumes a specific directory structure. In a real app we might query DB for paths.
    # For now, let's assume we can find them in output/clips/<novel_id>/<scene_id>/*.mp4
    # But we only have scene_id here. 
    # Let's search recursively in output/clips for the scene_id folder
    
    base_dir = config.OUTPUT_DIR / "clips"
    scene_dir = None
    
    # Simple search
    for d in base_dir.glob("*/*"):
        if d.name == scene_id:
            scene_dir = d
            break
            
    if not scene_dir:
        console.print(f"[red]Error: Could not find clip directory for scene {scene_id}[/red]")
        return
        
    clip_paths = sorted([str(p) for p in scene_dir.glob("*.mp4")])
    
    if not clip_paths:
        console.print(f"[red]Error: No mp4 clips found in {scene_dir}[/red]")
        return
        
    console.print(f"Found {len(clip_paths)} clips in {scene_dir}")
    console.print(f"Assembling to: {output}...")
    
    result = assembler.assemble_scene(scene_id, clip_paths, output)
    
    if result.success:
        console.print(f"[green]✓ Scene assembled successfully![/green]")
    else:
        console.print(f"[red]Error: {result.error}[/red]")


@cli.command()
@click.option('--novel-id', required=True, help='Novel UUID')
def phase4(novel_id):
    """Run full Phase 4: Generate & Assemble."""
    console.print("[bold cyan]Phase 4: Full Pipeline[/bold cyan]\n")
    
    ctx = click.get_current_context()
    
    # 1. Execute Queue
    console.print("[bold]Step 1: Executing Job Queue[/bold]")
    ctx.invoke(execute_queue, novel_id=novel_id, max_concurrent=5, resume=True)
    
    # 2. Assemble Scenes (Placeholder loop)
    # In a real implementation this would iterate over all scenes and assemble them
    console.print("\n[bold]Step 2: Assembling Scenes[/bold]")
    console.print("[yellow]Scene assembly in 'phase4' command is currently a placeholder. Use 'assemble-scene' for individual scenes.[/yellow]")


    # Export job queue JSON
    jobs_dir = Path(config.OUTPUT_DIR) / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    queue_path = jobs_dir / f"{title}_{api}_queue.json"
    job_queue.export_queue(novel_id, str(queue_path))
    console.print(f"[green]✓ Exported job queue to {queue_path}[/green]")

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold green]Phase 3 Complete![/bold green]")
    console.print(f"  Scenes processed: {len(breakdowns)}")
    console.print(f"  Prompts generated: {len(all_prompts)}")
    console.print(f"  Jobs queued: {len(jobs)}")
    console.print(f"  Estimated cost: ${cost.estimated_cost_usd:.2f} USD ({api})")
    console.print(f"  Estimated duration: {cost.total_duration_minutes} min of video")
    if validation["total_errors"] == 0:
        console.print("  Validation: [green]✓ PASSED[/green]")
    else:
        console.print(f"  Validation: [yellow]⚠ {validation['total_errors']} errors[/yellow]")
    console.print("=" * 60)


@cli.command('generate-prompts')
@click.option('--novel-id', required=True, help='Novel UUID')
def generate_prompts(novel_id: str):
    """Generate video prompts from scene breakdowns (Phase 3 Step 1 only)."""
    from prompts.video_prompt_engineer import VideoPromptEngineer

    console.print("[bold cyan]Generating video prompts...[/bold cyan]\n")
    db = Database()
    story_bible_data = db.get_story_bible(novel_id)
    if not story_bible_data:
        console.print("[red]Error: Story Bible not found.[/red]")
        return

    # Find breakdowns
    output_dir = Path(config.OUTPUT_DIR) / "scene_breakdowns"
    breakdown_path = None
    if output_dir.exists():
        for f in output_dir.glob("*_breakdown.json"):
            breakdown_path = f
            break
    if not breakdown_path:
        console.print("[red]Error: Scene breakdowns not found.[/red]")
        return

    with open(breakdown_path, 'r') as f:
        breakdowns = json.load(f)

    engineer = VideoPromptEngineer(story_bible_data)
    all_prompts = engineer.generate_prompts_for_all_scenes(breakdowns, novel_id)

    # Save prompts JSON
    title = story_bible_data.get("novel_title", "novel").lower().replace(" ", "_")
    prompts_dir = Path(config.OUTPUT_DIR) / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompts_path = prompts_dir / f"{title}_prompts.json"

    with open(prompts_path, 'w') as f:
        json.dump([p.model_dump() for p in all_prompts], f, indent=2)

    console.print(f"[green]✓ Generated {len(all_prompts)} prompts → {prompts_path}[/green]")


@cli.command('validate-prompts')
@click.option('--novel-id', required=True, help='Novel UUID')
def validate_prompts(novel_id: str):
    """Validate generated video prompts."""
    from prompts.validators import PromptValidator
    from extraction.models import VideoPrompt as VP

    console.print("[bold cyan]Validating video prompts...[/bold cyan]\n")

    # Load prompts from JSON
    prompts_dir = Path(config.OUTPUT_DIR) / "prompts"
    prompt_file = None
    if prompts_dir.exists():
        for f in prompts_dir.glob("*_prompts.json"):
            prompt_file = f
            break
    if not prompt_file:
        console.print("[red]Error: No prompts found. Run generate-prompts first.[/red]")
        return

    with open(prompt_file, 'r') as f:
        prompts_data = json.load(f)
    prompts = [VP(**p) for p in prompts_data]

    validation = PromptValidator.validate_all(prompts)

    console.print(f"Total prompts: {validation['total_prompts']}")
    console.print(f"Errors: {validation['total_errors']}")
    console.print(f"Warnings: {validation['total_warnings']}")
    console.print(f"All valid: {'[green]Yes[/green]' if validation['all_valid'] else '[red]No[/red]'}")

    # Character consistency
    for report in validation["consistency_reports"]:
        status = "[green]✓[/green]" if report.consistent_descriptions else "[yellow]⚠[/yellow]"
        console.print(f"  {status} {report.character_name}: {report.total_appearances} appearances")

    # Temporal
    temporal = validation["temporal_report"]
    status = "[green]✓[/green]" if temporal.is_coherent else "[yellow]⚠[/yellow]"
    console.print(f"  {status} Temporal coherence")
    for issue in temporal.issues:
        console.print(f"    [yellow]{issue}[/yellow]")


@cli.command('estimate-cost')
@click.option('--novel-id', required=True, help='Novel UUID')
@click.option('--api', default='seedance', help='API provider: seedance, kling, or runwayml')
def estimate_cost(novel_id: str, api: str):
    """Estimate video generation cost."""
    from generation.cost_estimator import CostEstimator
    from extraction.models import VideoPrompt as VP

    console.print("[bold cyan]Estimating generation cost...[/bold cyan]\n")

    prompts_dir = Path(config.OUTPUT_DIR) / "prompts"
    prompt_file = None
    if prompts_dir.exists():
        for f in prompts_dir.glob("*_prompts.json"):
            prompt_file = f
            break
    if not prompt_file:
        console.print("[red]Error: No prompts found.[/red]")
        return

    with open(prompt_file, 'r') as f:
        prompts = [VP(**p) for p in json.load(f)]

    estimator = CostEstimator(api_provider=api)
    cost = estimator.estimate_novel_cost(prompts)

    console.print(f"Clips: {cost.total_clips}")
    console.print(f"Video duration: {cost.total_duration_minutes} minutes")
    console.print(f"Estimated cost ({api}): [bold]${cost.estimated_cost_usd:.2f} USD[/bold]")

    console.print("\nProvider comparison:")
    for provider, prov_cost in estimator.compare_providers(prompts).items():
        console.print(f"  {provider}: ${prov_cost:.2f}")


@cli.command('export-prompts')
@click.option('--novel-id', required=True, help='Novel UUID')
@click.option('--output', default=None, help='Output path')
def export_prompts(novel_id: str, output: str):
    """Export generated prompts to JSON."""
    prompts_dir = Path(config.OUTPUT_DIR) / "prompts"
    prompt_file = None
    if prompts_dir.exists():
        for f in prompts_dir.glob("*_prompts.json"):
            prompt_file = f
            break
    if not prompt_file:
        console.print("[red]Error: No prompts found.[/red]")
        return

    if output:
        import shutil
        shutil.copy2(prompt_file, output)
        console.print(f"[green]✓ Exported prompts to {output}[/green]")
    else:
        console.print(f"[green]Prompts at: {prompt_file}[/green]")
        with open(prompt_file, 'r') as f:
            data = json.load(f)
        console.print(f"Total prompts: {len(data)}")


if __name__ == '__main__':
    cli()
