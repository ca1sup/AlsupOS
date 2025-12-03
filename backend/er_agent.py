# backend/er_agent.py
import logging
import asyncio
from typing import Dict

from backend.database import get_all_settings
# FIX: Import from the new er_db file instead of database.py
from backend.er_db import save_er_chart, get_er_patient_data
from backend.rag import get_ai_response, perform_rag_query
from backend.config import STEWARD_MEDICAL_FOLDER
from backend.prompts import (
    SCRIBE_SYSTEM_PROMPT, 
    ADVISOR_SYSTEM_PROMPT, 
    DEFAULT_CHART_TEMPLATE,
    ER_SEARCH_GENERATION_PROMPT,
    INTERVIEW_PROCESSOR_PROMPT
)

logger = logging.getLogger(__name__)

ER_STATUS: Dict[int, str] = {}

async def process_er_audio_update(patient_id: int, transcript: str):
    """
    Core Logic:
    1. Fetches Patient Data + Old Chart.
    2. Runs Interview Processor -> Clean/Diarize the raw audio transcript.
    3. Runs Scribe Agent -> Updates the Chart (HPI, MDM) based on cleaned dictation.
    4. Runs Search Generator -> Summarizes case into objective clinical terms.
    5. Runs RAG Search -> Fetches relevant docs using the summary.
    6. Runs Advisor Agent -> Analyzes Transcript + Full Chart + RAG Context.
    7. Saves everything to DB.
    """
    
    ER_STATUS[patient_id] = "Processing..."
    
    try:
        # 1. Fetch Context
        patient = await get_er_patient_data(patient_id)
        if not patient:
            logger.error(f"Patient {patient_id} not found.")
            ER_STATUS[patient_id] = "Error: Not Found"
            return

        current_chart = patient.get("chart_content", "") or ""
        
        # 2. Get Settings (for overrides)
        settings = await get_all_settings()
        
        # USE IMPORTED PROMPTS unless overridden in DB settings
        scribe_prompt = settings.get("er_scribe_prompt", SCRIBE_SYSTEM_PROMPT)
        advisor_prompt = settings.get("er_advisor_prompt", ADVISOR_SYSTEM_PROMPT)
        search_gen_prompt = settings.get("er_search_prompt", ER_SEARCH_GENERATION_PROMPT)
        interview_prompt = settings.get("er_interview_prompt", INTERVIEW_PROCESSOR_PROMPT)
        chart_template = settings.get("er_chart_template", DEFAULT_CHART_TEMPLATE)

        # 3. INTERVIEW PROCESSING: Clean and Diarize (NEW STEP)
        logger.info(f"Running Interview Processor for Patient {patient_id}...")
        cleaned_transcript = await get_ai_response([
            {"role": "system", "content": interview_prompt},
            {"role": "user", "content": transcript}
        ])
        
        # 4. SCRIBE: Construct Input & Run (Using CLEANED Transcript)
        scribe_user_msg = f"""
        Current Chart State:
        {current_chart if current_chart else "[New Patient]"}

        New Transcript/Update:
        "{cleaned_transcript}"

        Task: Update the chart. Follow the template structure strictly.
        Template:
        {chart_template}
        """

        # Run Scribe Inference
        logger.info(f"Running ER Scribe for Patient {patient_id}...")
        new_chart_content = await get_ai_response([
            {"role": "system", "content": scribe_prompt},
            {"role": "user", "content": scribe_user_msg}
        ])
        
        # Brief cooldown for Metal/GPU buffer
        await asyncio.sleep(0.5)

        # 5. SEARCH GENERATION: Summarize using CLEANED Transcript
        search_context_msg = f"Patient: {patient.get('age_sex')} {patient.get('complaint')}\nTranscript: {cleaned_transcript}"
        
        logger.info("Generating Clinical Search Summary...")
        search_query_response = await get_ai_response([
            {"role": "system", "content": search_gen_prompt},
            {"role": "user", "content": search_context_msg}
        ])
        
        # Clean up the response to get a raw query string
        search_query = search_query_response.strip().strip('"')
        logger.info(f"Generated RAG Query: {search_query}")

        # 6. RAG SEARCH: Retrieve Clinical Context using the Summary
        # Search explicitly in the Medical folder
        rag_docs, _ = await perform_rag_query(search_query, STEWARD_MEDICAL_FOLDER)
        rag_context_str = "\n\n".join(rag_docs) if rag_docs else "No specific clinical guidelines found in library."

        # 7. ADVISOR: Construct Input
        # It sees: 1. Full Patient Context (Chart), 2. Cleaned Dictation, 3. RAG Literature
        
        # Fallback to current_chart if scribe failed significantly (empty output)
        effective_chart = new_chart_content if new_chart_content and len(new_chart_content) > 20 else current_chart

        advisor_user_msg = f"""
        Patient Info: {patient.get('age_sex', 'Unknown')} - {patient.get('complaint', 'Unknown')}
        
        == LATEST UPDATE (Cleaned) ==
        "{cleaned_transcript}"
        
        == FULL CHART CONTEXT (History) ==
        {effective_chart}
        
        == RELEVANT LITERATURE (RAG Search Results) ==
        {rag_context_str}
        
        Task: Analyze the COMPLETE case history to provide clinical decision support.
        1. Evaluate the differentials in light of the RAG results.
        2. CRITICAL: For the #1 likely diagnosis, provide the Standard of Care treatment (Dose, Frequency, Duration) in the 'treatment_recommendations' section.
        3. Flag "Can't Miss" diagnoses.
        """

        # Run Advisor Inference
        logger.info(f"Running ER Advisor for Patient {patient_id}...")
        advisor_analysis = await get_ai_response([
            {"role": "system", "content": advisor_prompt},
            {"role": "user", "content": advisor_user_msg}
        ])

        # 8. Save & Notify
        # We save the cleaned transcript history implicitly in the chart, 
        # but you might want to save it explicitly later. For now, it drives the logic.
        await save_er_chart(patient_id, new_chart_content, advisor_analysis)
        ER_STATUS[patient_id] = "Ready"
        logger.info(f"ER Update Complete for {patient_id}")

    except Exception as e:
        logger.error(f"ER Agent Failed: {e}", exc_info=True)
        ER_STATUS[patient_id] = "Error"