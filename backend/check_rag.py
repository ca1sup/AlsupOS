# backend/check_rag.py
import asyncio
import os
import sys
import logging
from pathlib import Path
import numpy as np

# Force the script to see the backend package
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import CHROMA_PATH, WHOOSH_PATH, DOCS_PATH, EMBEDDING_MODEL_NAME
from backend.rag import get_chroma_client, get_whoosh_index, get_embedding_model
from whoosh.qparser import QueryParser
from backend.rag import WHOOSH_SCHEMA

# Mute warnings for the diagnostic
logging.basicConfig(level=logging.ERROR)

async def main():
    print(f"\n=== 🕵️ STEWARD DEEP DIAGNOSTIC ===")
    print(f"Target Model: {EMBEDDING_MODEL_NAME}")
    
    # 1. LOAD MODEL
    print("\n--- 1. LOADING EMBEDDING MODEL ---")
    try:
        model = await get_embedding_model()
        test_vec = await asyncio.to_thread(model.encode, "test")
        model_dim = test_vec.shape[1]
        print(f"✅ Model Loaded. Dimensions: {model_dim}")
    except Exception as e:
        print(f"❌ Model Load Failed: {e}")
        return

    # 2. CHROMA CHECK
    print("\n--- 2. CHECKING VECTOR DATABASE (CHROMA) ---")
    try:
        client = await get_chroma_client()
        cols = await asyncio.to_thread(client.list_collections)
        
        target_col = None
        for c in cols:
            if "Emergency" in c.name or "Medical" in c.name:
                target_col = c
                break
        
        if not target_col:
            print("❌ No 'Emergency' or 'Medical' collection found.")
        else:
            print(f"✅ Found Collection: [{target_col.name}]")
            count = await asyncio.to_thread(target_col.count)
            print(f"   - Document Count: {count}")
            
            if count > 0:
                # PEEK AT DATA
                peek = await asyncio.to_thread(target_col.peek, 1)
                if peek and 'embeddings' in peek:
                    stored_dim = len(peek['embeddings'][0])
                    print(f"   - Stored Vector Dimension: {stored_dim}")
                    
                    if stored_dim != model_dim:
                        print(f"\n   🚨 CRITICAL MISMATCH 🚨")
                        print(f"   Your config uses a {model_dim}-dim model, but DB has {stored_dim}-dim vectors.")
                        print(f"   -> Searches will ALWAYS fail.")
                        print(f"   -> FIX: You must re-ingest your documents or revert config.py to the old model.")
                    else:
                        print(f"   ✅ Dimensions Match ({stored_dim})")
                        
                        # TRY SEARCH
                        print(f"\n   ... Attempting Vector Search for 'appendicitis' ...")
                        query_vec = await asyncio.to_thread(model.encode, "appendicitis")
                        results = await asyncio.to_thread(
                            target_col.query,
                            query_embeddings=query_vec.tolist(),
                            n_results=3
                        )
                        if results['ids'] and len(results['ids'][0]) > 0:
                            print(f"   ✅ Vector Search SUCCESS. Found {len(results['ids'][0])} results.")
                            print(f"      Top Result: {results['metadatas'][0][0].get('filename', 'Unknown')}")
                        else:
                            print(f"   ❌ Vector Search returned 0 results (Logic Issue).")
    except Exception as e:
        print(f"❌ Chroma Check Failed: {e}")

    # 3. WHOOSH CHECK
    print("\n--- 3. CHECKING KEYWORD INDEX (WHOOSH) ---")
    try:
        ix = get_whoosh_index()
        with ix.searcher() as searcher:
            print(f"✅ Index Opened. Doc Count: {searcher.doc_count()}")
            
            q_str = "appendicitis"
            q = QueryParser("content", schema=WHOOSH_SCHEMA).parse(q_str)
            results = searcher.search(q, limit=3)
            
            if len(results) > 0:
                print(f"   ✅ Keyword Search SUCCESS for '{q_str}'. Found {len(results)} results.")
                print(f"      Top Result: {results[0].get('filename', 'Unknown')}")
            else:
                print(f"   ⚠️ Keyword Search found 0 hits for '{q_str}'.")
                print("      (This might be normal if the word isn't in the docs, but unlikely for 43k docs)")
                
    except Exception as e:
        print(f"❌ Whoosh Check Failed: {e}")

    print("\n=== DIAGNOSTIC COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())