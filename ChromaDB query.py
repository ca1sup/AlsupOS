import asyncio
from chromadb import PersistentClient
from pathlib import Path

async def diagnose():
    client = PersistentClient(path="./chroma_db")
    collections = client.list_collections()
    
    print(f"Total collections: {len(collections)}")
    for col in collections:
        print(f"\nCollection: {col.name}")
        print(f"  Metadata: {col.metadata}")
        print(f"  Count: {col.count()}")

asyncio.run(diagnose())