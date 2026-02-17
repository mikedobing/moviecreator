"""Quick script to get novel ID from database."""
import sqlite3

conn = sqlite3.connect('novel_pipeline.db')
cursor = conn.execute("SELECT id, title FROM novels")
for row in cursor:
    print(f"ID: {row[0]}")
    print(f"Title: {row[1]}")
    print()
conn.close()
