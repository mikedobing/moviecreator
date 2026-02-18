
import sqlite3
import config
from pathlib import Path

db_path = config.DB_PATH
novel_id = "c86f2802-10a3-4e02-9548-cece751a2fdb"

print(f"Checking DB at: {db_path}")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT bible_json FROM story_bibles WHERE novel_id = ?", (novel_id,)).fetchone()

if row:
    print("Found row.")
    bible_json = row['bible_json']
    print(f"Type: {type(bible_json)}")
    print(f"Content repr: {repr(bible_json)[:100]}...")
    if bible_json:
        print(f"First 100 chars: {bible_json[:100]}")
        try:
            import json
            data = json.loads(bible_json)
            print("JSON parse SUCCESS")
            print(f"Keys: {list(data.keys())}")
        except Exception as e:
            print(f"JSON parse FAILED: {e}")
            # Print around the error if possible?
else:
    print("No row found for novel_id.")

conn.close()
