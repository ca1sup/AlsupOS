# backend/memory.py
import logging
from backend.database import add_user_fact, get_all_settings
from backend.rag import get_ai_response

logger = logging.getLogger(__name__)

MEMORY_EXTRACTION_PROMPT = """You are a memory extraction system.
Your goal is to extract a standalone, factual statement from the user's input that is worth remembering long-term.
Ignore conversational filler.
If the user says "Remember that Isla likes purple", the fact is "Isla's favorite color is purple."
If the user says "Don't forget I have a meeting on Friday", the fact is "User has a meeting on Friday."

Return ONLY the fact as a single sentence. Do not add "Fact:" or quotes."""

async def extract_and_store_fact(user_input: str) -> str:
    """
    Uses the LLM to extract a fact from the user's input and saves it to the DB.
    Returns the extracted fact for confirmation.
    """
    try:
        settings = await get_all_settings()
        
        # 1. Extract Fact using LLM
        fact = await get_ai_response([
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": user_input}
        ], model=settings.get("llm_model"))
        
        cleaned_fact = fact.strip().strip('"')
        
        # 2. Store in DB
        if cleaned_fact:
            await add_user_fact(cleaned_fact)
            logger.info(f"Memory stored: {cleaned_fact}")
            return cleaned_fact
        else:
            return "Could not extract a fact."

    except Exception as e:
        logger.error(f"Memory extraction failed: {e}", exc_info=True)
        return "Failed to save memory."