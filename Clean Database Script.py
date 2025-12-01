import sqlite3

# Connect to database
conn = sqlite3.connect('steward.db')
cursor = conn.cursor()

print("Cleaning chunks table...")
# Delete all RAG chunks (we will re-ingest them anyway)
cursor.execute("DELETE FROM chunks;")
cursor.execute("DELETE FROM documents;")
conn.commit()

print("Vacuuming database (this may take a while)...")
# Reclaims disk space
cursor.execute("VACUUM;") 

conn.close()
print("Done! Check your file size now.")