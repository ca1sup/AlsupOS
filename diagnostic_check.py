#!/usr/bin/env python3
"""
Diagnostic script to check RAG system health
Run from project root: python diagnostic_check.py
"""
import asyncio
import aiosqlite
from pathlib import Path
from chromadb import PersistentClient

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "chroma_db"
DOCS_PATH = BASE_DIR / "docs"
DB_STEWARD_PATH = BASE_DIR / "steward.db"

async def check_filesystem():
    """Check what files exist on disk"""
    print("\n=== FILESYSTEM CHECK ===")
    
    if not DOCS_PATH.exists():
        print(f"❌ DOCS_PATH doesn't exist: {DOCS_PATH}")
        return
    
    folders = [d for d in DOCS_PATH.iterdir() if d.is_dir()]
    print(f"✓ Found {len(folders)} folders in docs/")
    
    for folder in folders:
        files = list(folder.rglob("*.md")) + list(folder.rglob("*.txt"))
        print(f"  - {folder.name}: {len(files)} .md/.txt files")

async def check_chromadb():
    """Check ChromaDB collections"""
    print("\n=== CHROMADB CHECK ===")
    
    if not DB_PATH.exists():
        print(f"❌ ChromaDB path doesn't exist: {DB_PATH}")
        return
    
    try:
        client = PersistentClient(path=str(DB_PATH))
        collections = client.list_collections()
        
        print(f"✓ Found {len(collections)} collections in ChromaDB")
        
        for col in collections:
            count = col.count()
            metadata = col.metadata or {}
            pretty_name = metadata.get("pretty_name", "NO METADATA")
            print(f"  - {col.name} ('{pretty_name}'): {count} chunks")
            
            if count == 0:
                print(f"    ⚠️  WARNING: Collection is empty!")
                
    except Exception as e:
        print(f"❌ Failed to read ChromaDB: {e}")

async def check_sqlite():
    """Check SQLite tracking database"""
    print("\n=== SQLITE CHECK ===")
    
    if not DB_STEWARD_PATH.exists():
        print(f"❌ SQLite DB doesn't exist: {DB_STEWARD_PATH}")
        return
    
    try:
        async with aiosqlite.connect(DB_STEWARD_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Check documents table
            cursor = await conn.execute("""
                SELECT collection_name, status, COUNT(*) as count
                FROM documents
                GROUP BY collection_name, status
            """)
            rows = await cursor.fetchall()
            
            print("Document Status by Collection:")
            for row in rows:
                print(f"  - {row['collection_name']} ({row['status']}): {row['count']} files")
            
            # Check for chunks
            cursor = await conn.execute("SELECT COUNT(*) as count FROM chunks")
            chunk_count = (await cursor.fetchone())['count']
            print(f"\n✓ Total chunks in database: {chunk_count}")
            
            # Check for orphaned files (in filesystem but not in DB)
            cursor = await conn.execute("""
                SELECT DISTINCT collection_name, file_name
                FROM documents
                WHERE status = 'active'
            """)
            db_files = {(row['collection_name'], row['file_name']) for row in await cursor.fetchall()}
            
            print(f"\n✓ Tracked files in DB: {len(db_files)}")
            
    except Exception as e:
        print(f"❌ Failed to read SQLite: {e}")

async def check_api_compatibility():
    """Check if collections are compatible with API"""
    print("\n=== API COMPATIBILITY CHECK ===")
    
    try:
        from backend.config import sanitize_collection_name
        
        if not DOCS_PATH.exists():
            return
        
        print("Checking collection name sanitization:")
        for folder in DOCS_PATH.iterdir():
            if folder.is_dir():
                sanitized = sanitize_collection_name(folder.name)
                if sanitized != folder.name.lower().replace(" ", "_"):
                    print(f"  ⚠️  {folder.name} -> {sanitized}")
                else:
                    print(f"  ✓ {folder.name}")
                    
    except Exception as e:
        print(f"❌ Import error: {e}")

async def main():
    print("=" * 60)
    print("RAG SYSTEM DIAGNOSTIC TOOL")
    print("=" * 60)
    
    await check_filesystem()
    await check_chromadb()
    await check_sqlite()
    await check_api_compatibility()
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())