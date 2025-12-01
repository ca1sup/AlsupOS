import logging
import json
from typing import Optional, List
from backend.rag import perform_rag_query, generate_stream, get_ai_response
from backend.config import sanitize_collection_name
from backend.prompts import PERSONA_DEFAULTS, ROUTER_SYSTEM_PROMPT
from backend.database import get_personas

logger = logging.getLogger(__name__)

async def determine_search_scope(query: str, default_folder: str, persona_name: str) -> List[str]:
    """
    Intelligently routes the query to specific folders if the default is 'all'.
    """
    # If the user/persona already picked a specific folder (e.g. "Clinical"), respect it.
    if default_folder != "all":
        return [default_folder]
    
    # If we are in "God Mode" (Vault) or "Steward" (General), try to route intelligently.
    # We skip routing for very short queries to save latency.
    if len(query.split()) < 3:
        return ["all"]

    try:
        # Ask the LLM to classify the query
        # We use a bare-bones call to minimize latency
        response = await get_ai_response([
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ])
        
        # Clean and Parse JSON
        clean_json = response.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0]
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1]
            
        folders = json.loads(clean_json)
        
        if isinstance(folders, list) and len(folders) > 0:
            # If the router says "all", we return "all" to trigger the fallback logic later
            return folders
            
        return ["all"]

    except Exception as e:
        logger.warning(f"Router failed: {e}. Falling back to 'all'.")
        return ["all"]


async def agent_stream(
    query: str, 
    session_id: int, 
    persona: str, 
    folder: str, 
    file: Optional[str] = None
):
    """
    Direct-RAG Pipeline with UI Thinking Blocks & Intelligent Routing.
    """
    logger.info(f"Direct RAG Request ({persona}): {query}")
    
    # === 1. Fetch Configuration ===
    try:
        db_personas = await get_personas()
        persona_map = {p['name']: p.get('default_folder', 'all') for p in db_personas}
        prompt_map = {p['name']: p['prompt'] for p in db_personas}
    except Exception as e:
        logger.error(f"Failed to fetch personas from DB: {e}")
        persona_map = {}
        prompt_map = {}

    # === 2. Determine Initial Scope ===
    # Priority A: User manually selected a folder in UI
    if folder and folder != "all":
        initial_scope = [folder]
        routing_explanation = f"User selected '{folder}'."
    else:
        # Priority B: Use Persona Default
        default = persona_map.get(persona, "all")
        initial_scope = [default]
        routing_explanation = f"Using {persona} default."

    # === START THINKING BLOCK ===
    yield "<think>\n"
    
    # === 3. Intelligent Routing (The "Brain") ===
    folders_to_search = initial_scope
    
    # Only run the router if we are starting with "all" (Generic Search)
    if initial_scope == ["all"]:
        yield "🧠 Analyzing query intent...\n"
        routed_folders = await determine_search_scope(query, "all", persona)
        
        if routed_folders != ["all"]:
            folders_to_search = routed_folders
            yield f"👉 Routing search to: {', '.join(folders_to_search)}\n"
        else:
            yield "🌐 Performing broad search (All Folders)...\n"
    else:
        yield f"🔍 Searching scope: {', '.join(folders_to_search)}\n"

    # === 4. Execute Search ===
    all_rag_chunks = []
    all_metas = []
    
    try:
        # A. Primary Search (Routed Folders)
        for folder_name in folders_to_search:
            rag_chunks, metas = await perform_rag_query(query, folder_name, file)
            if rag_chunks:
                all_rag_chunks.extend(rag_chunks)
                all_metas.extend(metas)
        
        # B. Fallback Search (The "Nuclear Option")
        # If the routed search failed (e.g. Router guessed "Finance" but answer was in "Inbox"),
        # we fall back to searching EVERYTHING to ensure we don't miss the answer.
        if not all_rag_chunks and "all" not in folders_to_search:
            yield f"⚠️ No docs found in {', '.join(folders_to_search)}. Expanding to ALL folders...\n"
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

    # === 5. Format Context ===
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
        
        # Context Limit
        final_context_chunks = all_rag_chunks[:25]

    yield "</think>\n"
    # === END THINKING BLOCK ===

    # 6. Select Prompt & Generate
    if persona in prompt_map:
        sys_prompt = prompt_map[persona]
    elif persona in PERSONA_DEFAULTS:
        sys_prompt = PERSONA_DEFAULTS[persona]["system_prompt"]
    else:
        sys_prompt = PERSONA_DEFAULTS["Steward"]["system_prompt"]

    async for token in generate_stream(
        query=query, 
        context=final_context_chunks, 
        history=[], 
        persona_name=persona 
    ):
        yield token