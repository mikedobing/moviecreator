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


if __name__ == '__main__':
    cli()

