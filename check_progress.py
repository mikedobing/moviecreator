"""Enhanced progress checker that estimates extraction progress."""
import sqlite3
from pathlib import Path
from datetime import datetime

db_path = Path("./output/pipeline.db")

if not db_path.exists():
    print("❌ No database found yet")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get novel info
cursor.execute("SELECT title, page_count, word_count FROM novels LIMIT 1")
novel_info = cursor.fetchone()

# Get chunks
cursor.execute("SELECT COUNT(*) FROM chunks")
chunk_count = cursor.fetchone()[0]

# Check pipeline runs
cursor.execute("""
    SELECT phase, status, started_at, completed_at 
    FROM pipeline_runs 
    ORDER BY started_at DESC
""")
runs = cursor.fetchall()

# Check if story bible exists
cursor.execute("SELECT COUNT(*) FROM story_bibles")
bible_count = cursor.fetchone()[0]

conn.close()

print("=" * 70)
print("📊 DETAILED PIPELINE PROGRESS")
print("=" * 70)

if novel_info:
    print(f"\n📖 Novel: {novel_info[0]}")
    print(f"   Pages: {novel_info[1]} | Words: {novel_info[2]:,}")

print(f"\n✓ Chunks created: {chunk_count}")

# Estimate progress based on chunk count and expected API calls
# Character extraction: chunks ÷ 5 batches
# Locations extraction: chunks ÷ 5 batches  
# Tone/plot/etc: ~10-15 sample chunk calls
char_batches = chunk_count // 5 + (1 if chunk_count % 5 else 0)
loc_batches = chunk_count // 5 + (1 if chunk_count % 5 else 0)
total_calls_estimate = char_batches + loc_batches + 15  # +15 for tone, plot, etc.

print(f"\n🔄 Extraction Progress Estimate:")
print(f"   Total API calls needed: ~{total_calls_estimate}")
print(f"   ")
print(f"   Character batches: {char_batches} calls (~{char_batches * 3} seconds)")
print(f"   Location batches: {loc_batches} calls (~{loc_batches * 3} seconds)")
print(f"   Tone/Plot/etc: ~15 calls (~45 seconds)")
print(f"   Deduplication: 1 final call (~5 seconds)")
print(f"   ")
print(f"   Estimated total time: ~{(total_calls_estimate * 3) // 60}-{(total_calls_estimate * 5) // 60} minutes")

if bible_count > 0:
    print(f"\n✅ Story Bible: COMPLETE!")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT bible_json FROM story_bibles LIMIT 1")
    import json
    bible_json = cursor.fetchone()[0]
    bible = json.loads(bible_json)
    conn.close()
    
    print(f"\n   📝 Characters: {len(bible.get('characters', []))}")
    print(f"   🏛️  Locations: {len(bible.get('locations', []))}")
    print(f"   🎬 Genre: {', '.join(bible.get('tone', {}).get('genre', []))}")
else:
    print(f"\n⏳ Story Bible: IN PROGRESS...")
    print(f"\n   💡 TIP: Check the main terminal window to see current stage:")
    print(f"      - 'Extracting characters...'")
    print(f"      - 'Extracting locations...'")
    print(f"      - 'Extracting tone...'")
    print(f"      - 'Merging character profiles...'")

if runs:
    print(f"\n📋 Pipeline Runs:")
    for phase, status, started, completed in runs[:3]:
        print(f"   {phase}: {status} (started: {started[:19] if started else 'N/A'})")

print("\n" + "=" * 70)
print("Run this script again in 1-2 minutes to check progress")
print("=" * 70)
