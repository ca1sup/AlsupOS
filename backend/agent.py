import logging
import json
from typing import Optional, List, Dict
from backend.rag import perform_rag_query, generate_stream
from backend.database import get_all_settings
from backend.config import sanitize_collection_name

logger = logging.getLogger(__name__)

async def agent_stream(
    query: str, 
    session_id: int, 
    persona: str, 
    folder: str, 
    file: Optional[str] = None,
    history: List[Dict[str, str]] = [] 
):
    """
    Direct-RAG Pipeline with UI Thinking Blocks & Robust Fallback.
    """
    logger.info(f"Direct RAG Request ({persona}): {query}")
    
    settings = await get_all_settings()
    
    # 1. Determine Search Scope
    folders_to_search = []
    
    # Priority: User selection in UI
    if folder and folder != "all":
        folders_to_search = [folder]
    else:
        # Fallback: Persona Defaults from DB
        try:
            persona_map = json.loads(settings.get("persona_folder_map", "{}"))
        except:
            persona_map = {}
            
        folders_to_search = persona_map.get(persona, ["all"])

    # === START THINKING BLOCK ===
    yield "<think>\n"
    yield f"🔍 Searching contexts: {', '.join(folders_to_search)}...\n"
    
    all_rag_chunks = []
    all_metas = []
    
    try:
        # A. Primary Search
        for folder_name in folders_to_search:
            rag_chunks, metas = await perform_rag_query(query, folder_name, file)
            
            if rag_chunks:
                all_rag_chunks.extend(rag_chunks)
                all_metas.extend(metas)
        
        # B. Fallback Search (The "Nuclear Option")
        if not all_rag_chunks and "all" not in folders_to_search:
            yield f"⚠️ No docs found in {folders_to_search[0]}. Expanding search to ALL folders...\n"
            fallback_chunks, fallback_metas = await perform_rag_query(query, "all", file)
            
            if fallback_chunks:
                all_rag_chunks = fallback_chunks
                all_metas = fallback_metas
                yield "✅ Found documents via backup search.\n"
            else:
                yield "❌ Backup search also returned 0 results.\n"

    except Exception as e:
        logger.error(f"Search failed: {e}")
        yield f"⚠️ Search error: {e}\n"

    # 3. Format Context for LLM
    final_context_chunks = []
    if not all_rag_chunks:
        yield "ℹ️ No documents found. Relying on general knowledge.\n"
    else:
        # Generate Structured Sources for UI
        sources_data = []
        for i, m in enumerate(all_metas[:5]):
            fname = m.get('filename', 'Doc')
            page = m.get('page', 0)
            raw_chunk = all_rag_chunks[i] if i < len(all_rag_chunks) else ""
            snippet = " ".join(raw_chunk.split())[:300] + "..."
            
            sources_data.append({
                "file": fname,
                "page": page,
                "snippet": snippet
            })
        
        if sources_data:
            yield {"type": "sources", "data": sources_data}
        
        final_context_chunks = all_rag_chunks[:25]

    yield "</think>\n"

    # 4. Determine Memory Depth
    memory_depth = int(settings.get("memory_depth", 10))
    effective_history = history[-memory_depth:] if memory_depth > 0 else []

    # 5. Stream LLM Response
    async for token in generate_stream(
        query=query, 
        context=final_context_chunks, 
        history=effective_history, 
        persona_name=persona 
    ):
        yield token