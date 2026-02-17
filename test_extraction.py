"""Test character extraction with just ONE batch of chunks."""
import json
from anthropic import Anthropic
from dotenv import load_dotenv
import os

load_dotenv()

# Get first 5 chunks from database
import sqlite3
conn = sqlite3.connect("./output/pipeline.db")
cursor = conn.cursor()

cursor.execute("SELECT text FROM chunks ORDER BY chapter_number, chunk_index LIMIT 5")
chunks = [row[0] for row in cursor.fetchall()]
conn.close()

print(f"Testing with {len(chunks)} chunks...")
print(f"First chunk preview: {chunks[0][:200]}...")

# Create prompt
from extraction import prompts
prompt = prompts.character_extraction_prompt(chunks)

print(f"\nPrompt length: {len(prompt)} characters")
print(f"Sending to Claude...")

# Call API
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

try:
    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response = message.content[0].text
    
    print(f"\n✓ Got response ({len(response)} chars)")
    print(f"\nFirst 500 chars of response:")
    print("=" * 70)
    print(response[:500])
    print("=" * 70)
    
    # Try to parse as JSON
    print("\nAttempting to parse as JSON...")
    try:
        data = json.loads(response)
        print(f"✓ Valid JSON! Found {len(data)} characters")
    except json.JSONDecodeError as e:
        print(f"✗ JSON parse failed: {e}")
        print("\nTrying to extract JSON from response...")
        
        # Try markdown extraction
        if "```json" in response:
            extracted = response.split("```json")[1].split("```")[0].strip()
            print(f"Extracted from ```json block:")
            print(extracted[:300])
            try:
                data = json.loads(extracted)
                print(f"✓ Successfully extracted! Found {len(data)} characters")
            except:
                print(f"✗ Still can't parse")
        else:
            print("No ```json blocks found")
            
except Exception as e:
    print(f"\n✗ API call failed: {e}")
