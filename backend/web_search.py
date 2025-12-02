# backend/web_search.py
import logging
import asyncio
import json
from typing import List, Optional
from backend.rag import get_ai_response
from backend.database import get_all_settings

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Suppress noisy logs
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
logging.getLogger("ddgs").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def perform_web_search(query: str, model: str) -> str:
    """
    Standard web search for general queries (Steward).
    """
    return await _execute_search(query, model, context_label="SEARCH RESULTS")

async def perform_medical_search(query: str, model: str, sites: Optional[List[str]] = None) -> str:
    """
    Restricted search to high-value EM resources.
    """
    # 1. Prefer explicitly passed sites
    if sites and len(sites) > 0:
        target_sites = sites
    else:
        # 2. Fallback to Database Settings
        settings = await get_all_settings()
        try:
            stored_sites = json.loads(settings.get("web_search_trusted_sites", "[]"))
            if stored_sites:
                target_sites = stored_sites
            else:
                # 3. Hard Fallback
                target_sites = [
                    "site:wikiem.com", 
                    "site:litfl.com", 
                    "site:mdcalc.com", 
                    "site:uptodate.com",
                    "site:ncbi.nlm.nih.gov",
                    "site:merckmanuals.com"
                ]
        except:
            target_sites = ["site:wikiem.com", "site:litfl.com"]

    # Normalize "site:" prefix
    final_sites = []
    for s in target_sites:
        if not s.strip(): continue
        if s.startswith("site:"): final_sites.append(s)
        else: final_sites.append(f"site:{s}")

    site_operator = " OR ".join(final_sites)
    targeted_query = f"({site_operator}) {query}"
    
    logger.info(f"🏥 Performing Medical Search for: {query} (Scope: {len(final_sites)} sites)")
    return await _execute_search(targeted_query, model, context_label="MEDICAL GUIDELINES")

async def _execute_search(query: str, model: str, context_label: str) -> str:
    logger.info(f"Searching web for: {query}")
    try:
        def _search():
            with DDGS() as ddgs:
                try:
                    return list(ddgs.text(query, region="us-en", max_results=10))
                except TypeError:
                    return list(ddgs.text(query, max_results=10))
        
        results = await asyncio.to_thread(_search)
        
        if not results:
            return f"No web results found for '{query}'."

        context_str = ""
        for i, res in enumerate(results):
            title = res.get('title', 'No Title')
            body = res.get('body', 'No Content')
            href = res.get('href', '#')
            context_str += f"[Source {i+1}]\nTitle: {title}\nURL: {href}\nContent: {body}\n\n"

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
        
        summary = await get_ai_response([
            {"role": "system", "content": "You are a helpful research assistant. You answer based on facts provided."},
            {"role": "user", "content": prompt}
        ], model=model)
        
        return summary

    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        return f"I encountered an error while searching the web: {str(e)}"