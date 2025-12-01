# backend/web_search.py
import logging
import asyncio
from typing import List, Optional
from backend.rag import get_ai_response

# Handle library renaming (ddgs is the new package name)
# This try/except block ensures the app doesn't crash if the library updates
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Suppress noisy logs from the search library to keep your console clean
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
logging.getLogger("ddgs").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def perform_web_search(query: str, model: str) -> str:
    """
    Standard web search for general queries (Steward).
    Uses the "SEARCH RESULTS" label for the context.
    """
    return await _execute_search(query, model, context_label="SEARCH RESULTS")

async def perform_medical_search(query: str, model: str, sites: Optional[List[str]] = None) -> str:
    """
    Restricted search to high-value EM resources.
    If 'sites' is provided, it restricts the search ONLY to those domains.
    If 'sites' is empty/None, it falls back to a curated list of trusted EM sites.
    """
    if sites and len(sites) > 0:
        # User-defined approved sites
        target_sites = []
        for s in sites:
            if not s.strip(): continue
            # Handle if user typed "site:wikiem.com" or just "wikiem.com"
            if s.startswith("site:"):
                target_sites.append(s)
            else:
                target_sites.append(f"site:{s}")
    else:
        # Default fallback if no custom sources defined
        target_sites = [
            "site:wikiem.com", 
            "site:litfl.com", 
            "site:mdcalc.com", 
            "site:uptodate.com",
            "site:ncbi.nlm.nih.gov",
            "site:merckmanuals.com"
        ]

    # Construct a query that restricts results to these domains
    site_operator = " OR ".join(target_sites)
    targeted_query = f"({site_operator}) {query}"
    
    logger.info(f"🏥 Performing Medical Search for: {query} (Scope: {len(target_sites)} sites)")
    return await _execute_search(targeted_query, model, context_label="MEDICAL GUIDELINES")

async def _execute_search(query: str, model: str, context_label: str) -> str:
    """
    Shared internal search execution logic.
    Executes the search via DuckDuckGo and synthesizes an answer using the LLM.
    """
    logger.info(f"Searching web for: {query}")
    try:
        # 1. Search DDG (Sync function, run in thread to avoid blocking the server)
        def _search():
            with DDGS() as ddgs:
                # Try/catch for potential API changes between versions
                try:
                    # 'region="us-en"' ensures results are relevant to your location (Salt Lake City context)
                    # max_results=10 gives the LLM enough breadth to find the answer
                    return list(ddgs.text(query, region="us-en", max_results=10))
                except TypeError:
                    # Fallback for older versions of the library
                    return list(ddgs.text(query, max_results=10))
        
        results = await asyncio.to_thread(_search)
        
        if not results:
            return f"No web results found for '{query}'."

        # 2. Format results for LLM
        # We create a structured text block so the LLM knows exactly which source is which
        context_str = ""
        for i, res in enumerate(results):
            title = res.get('title', 'No Title')
            body = res.get('body', 'No Content')
            href = res.get('href', '#')
            context_str += f"[Source {i+1}]\nTitle: {title}\nURL: {href}\nContent: {body}\n\n"

        # 3. Summarize / Synthesize
        # This prompt forces the "Grounding" behavior you liked in the Azure article
        prompt = f"""You are a Web Search Agent. 
Your goal is to answer the user's question based ONLY on the provided search results.

User Question: "{query}"

Instructions:
1. Synthesize the information into a clear, direct answer.
2. If the search results have conflicting information, note the conflict.
3. Cite your sources using the format [Source X].
4. If the results do not contain the answer, state "I could not find a specific answer in the search results."

--- {context_label} ---
{context_str}
"""
        
        # Use the configured model to generate the answer
        summary = await get_ai_response([
            {"role": "system", "content": "You are a helpful research assistant. You answer based on facts provided."},
            {"role": "user", "content": prompt}
        ], model=model)
        
        return summary

    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        # Return a friendly error message so the chat doesn't just break
        return f"I encountered an error while searching the web: {str(e)}"