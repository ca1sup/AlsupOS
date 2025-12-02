import logging
from typing import Optional, List, Dict
from backend.rag import perform_rag_query, generate_stream
from backend.database import get_all_settings
from backend.config import (
    STEWARD_MEDICAL_FOLDER, 
    STEWARD_FINANCE_FOLDER,
    STEWARD_HEALTH_FOLDER,
    STEWARD_WORKOUT_FOLDER,
    STEWARD_MEALPLANS_FOLDER,
    STEWARD_JOURNAL_FOLDER,
    STEWARD_CONTEXT_FOLDER,
    sanitize_collection_name
)
from backend.prompts import (
    VAULT_SYSTEM_PROMPT, 
    MENTOR_SYSTEM_PROMPT, 
    STEWARD_SYSTEM_PROMPT,
    STEWARD_HEALTH_PROMPT,
    STEWARD_FINANCE_PROMPT
)

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Maps Personas to their default knowledge base folders
PERSONA_FOLDER_MAP = {
    "Clinical": [STEWARD_MEDICAL_FOLDER],
    "CFO": [STEWARD_FINANCE_FOLDER],
    "Coach": [STEWARD_HEALTH_FOLDER, STEWARD_WORKOUT_FOLDER, STEWARD_MEALPLANS_FOLDER],
    "Mentor": [STEWARD_JOURNAL_FOLDER, STEWARD_CONTEXT_FOLDER],
    "Steward": ["all"],
    "Vault": ["all"]
}

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
        # Fallback: Persona Defaults
        folders_to_search = PERSONA_FOLDER_MAP.get(persona, ["all"])

    # === START THINKING BLOCK ===
    # The <think> tag triggers the bouncing orb UI
    yield "<think>\n"
    yield f"🔍 Searching contexts: {', '.join(folders_to_search)}...\n"
    
    all_rag_chunks = []
    all_metas = []
    
    try:
        # A. Primary Search
        for folder_name in folders_to_search:
            # We pass the raw folder name; rag.py handles sanitization & fuzzy match
            rag_chunks, metas = await perform_rag_query(query, folder_name, file)
            
            if rag_chunks:
                all_rag_chunks.extend(rag_chunks)
                all_metas.extend(metas)
        
        # B. Fallback Search (The "Nuclear Option")
        # If specific folders yielded 0 chunks, force a search on EVERYTHING.
        # This fixes issues where docs were accidentally ingested into 'Inbox' or 'default'.
        if not all_rag_chunks and "all" not in folders_to_search:
            yield f"⚠️ No docs found in {folders_to_search[0]}. Expanding search to ALL folders...\n"
            # Explicitly pass 'all' to perform_rag_query to trigger the new 'all' handler
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
        # Generate Structured Sources for UI (Chips with Hover)
        sources_data = []
        for i, m in enumerate(all_metas[:5]): # Limit to top 5 sources
            fname = m.get('filename', 'Doc')
            page = m.get('page', 0)
            
            # Extract a snippet for the tooltip (clean up newlines)
            raw_chunk = all_rag_chunks[i] if i < len(all_rag_chunks) else ""
            snippet = " ".join(raw_chunk.split())[:300] + "..."
            
            sources_data.append({
                "file": fname,
                "page": page,
                "snippet": snippet
            })
        
        # Yield the structured data (dict) instead of text
        if sources_data:
            yield {"type": "sources", "data": sources_data}
        
        # DEV FIX #1: Context Limit via CHUNK COUNT, not Characters
        # Keep top 25 chunks (approx 12k tokens, safe for Phi-4/Llama-3)
        final_context_chunks = all_rag_chunks[:25]

    # === END THINKING BLOCK ===
    yield "</think>\n"

    # 4. Select Persona Prompt
    sys_prompt = STEWARD_SYSTEM_PROMPT
    if persona == "Clinical":
        # DEV FIX #3: Authoritative System Prompt
        sys_prompt = """You are an expert Emergency Medicine physician.
Use ONLY the following context to answer. 
If the context does not contain relevant information, say "I do not have sufficient context to answer accurately."
Answer the user's question based strictly on the provided context."""
    elif persona == "Mentor":
        sys_prompt = MENTOR_SYSTEM_PROMPT
    elif persona == "Vault":
        sys_prompt = VAULT_SYSTEM_PROMPT
    elif persona == "Coach":
        sys_prompt = STEWARD_HEALTH_PROMPT
    elif persona == "CFO":
        sys_prompt = STEWARD_FINANCE_PROMPT

    # 5. Determine Memory Depth
    # Read from settings, default to 10 messages if not set
    memory_depth = int(settings.get("memory_depth", 10))
    
    # Slice the history to respect the user's setting
    effective_history = history[-memory_depth:] if memory_depth > 0 else []

    # 6. Stream LLM Response
    # Pass LIST of chunks to generate_stream, preventing premature concatenation issues
    async for token in generate_stream(
        query=query, 
        context=final_context_chunks, 
        history=effective_history, # Pass the history!
        persona_name=persona 
    ):
        yield token