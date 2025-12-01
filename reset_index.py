import os
import shutil
import sqlite3
from pathlib import Path
from backend.config import DB_PATH, CHROMA_PATH, WHOOSH_PATH

def reset_rag_data():
    print("⚠️  STARTING RAG RESET ⚠️")
    print("This will clear your search index and force a full re-ingest.")
    
    # 1. Clear Database Records
    if DB_PATH.exists():
        print(f"🧹 Cleaning Database Records in {DB_PATH.name}...")
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Delete RAG-specific tables only
            cursor.execute("DELETE FROM documents")
            cursor.execute("DELETE FROM chunks")
            conn.commit()
            conn.close()
            print("   ✅ Documents and Chunks tables cleared.")
        except Exception as e:
            print(f"   ❌ Error cleaning DB: {e}")

    # 2. Delete Vector Database (Chroma)
    if CHROMA_PATH.exists():
        print(f"🔥 Deleting Vector DB at {CHROMA_PATH}...")
        try:
            shutil.rmtree(CHROMA_PATH)
            print("   ✅ Chroma DB deleted.")
        except Exception as e:
            print(f"   ❌ Error deleting Chroma: {e}")

    # 3. Delete Keyword Index (Whoosh)
    if WHOOSH_PATH.exists():
        print(f"🔥 Deleting Keyword Index at {WHOOSH_PATH}...")
        try:
            shutil.rmtree(WHOOSH_PATH)
            print("   ✅ Whoosh Index deleted.")
        except Exception as e:
            print(f"   ❌ Error deleting Whoosh: {e}")

    print("\n✨ RESET COMPLETE. You can now trigger the Ingest process to rebuild everything.")

if __name__ == "__main__":
    reset_rag_data()