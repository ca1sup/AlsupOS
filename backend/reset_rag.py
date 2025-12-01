import sqlite3
import shutil
import os
import logging
from pathlib import Path

# Setup simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Cleaner")

# Define Paths manually to ensure this script runs standalone if needed
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "steward.db"
CHROMA_PATH = BASE_DIR / "chroma_db"
WHOOSH_PATH = BASE_DIR / "whoosh_index"

def clean_rag_data():
    logger.info("🧹 Starting Surgical RAG Cleanup...")

    # 1. Clean SQLite RAG Tables
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Count before deletion
            cursor.execute("SELECT COUNT(*) FROM documents")
            result = cursor.fetchone()
            doc_count = result[0] if result else 0
            
            logger.info(f"  [DB] Found {doc_count} documents. Cleaning tables...")

            # Delete RAG-specific data only
            cursor.execute("DELETE FROM chunks")
            cursor.execute("DELETE FROM documents")
            conn.commit() # Commit the deletions explicitly
            
            # Switch to autocommit mode to run VACUUM
            conn.isolation_level = None
            logger.info("  [DB] Vacuuming database to reclaim space...")
            cursor.execute("VACUUM")
            
            conn.close()
            logger.info("  [DB] ✅ SQLite 'documents' and 'chunks' tables cleared and vacuumed.")
        except Exception as e:
            logger.error(f"  [DB] ❌ Database Error: {e}")
    else:
        logger.info("  [DB] Database not found, skipping.")

    # 2. Delete ChromaDB (Vector Store)
    if CHROMA_PATH.exists():
        try:
            shutil.rmtree(CHROMA_PATH)
            logger.info("  [FS] ✅ ChromaDB folder deleted.")
        except Exception as e:
            logger.error(f"  [FS] ❌ Could not delete ChromaDB: {e}")
    else:
        logger.info("  [FS] ChromaDB folder not found, skipping.")

    # 3. Delete Whoosh (Keyword Index)
    if WHOOSH_PATH.exists():
        try:
            shutil.rmtree(WHOOSH_PATH)
            logger.info("  [FS] ✅ Whoosh index folder deleted.")
        except Exception as e:
            logger.error(f"  [FS] ❌ Could not delete Whoosh index: {e}")
    else:
        logger.info("  [FS] Whoosh index folder not found, skipping.")

    logger.info("\n✨ Cleanup Complete. You can now run ingest.command safely with the new model.")

if __name__ == "__main__":
    clean_rag_data()