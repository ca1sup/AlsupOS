# backend/er_agent.py
import logging
import asyncio
from typing import Dict

from backend.database import get_all_settings
# FIX: Import from the new er_db file instead of database.py
from backend.er_db import save_er_chart, get_er_patient_data
from backend.rag import get_ai_response
from backend.prompts import (
    SCRIBE_SYSTEM_PROMPT, 
    ADVISOR_SYSTEM_PROMPT, 
    DEFAULT_CHART_TEMPLATE
)

logger = logging.getLogger(__name__)

ER_STATUS: Dict[int, str] = {}

async def process_er_audio_update(patient_id: int, transcript: str):
    """
    Core Logic:
    1. Fetches Patient Data + Old Chart
    2. Runs TWO parallel agents:
       - Scribe: Updates the Chart (HPI, MDM)
       - Advisor: Analyzes for Safety/Suggestions
    3. Merges output -> Saves to DB
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
        chart_template = settings.get("er_chart_template", DEFAULT_CHART_TEMPLATE)

        # 3. Construct Inputs
        
        # SCRIBE INPUT
        scribe_user_msg = f"""
        Current Chart State:
        {current_chart if current_chart else "[New Patient]"}

        New Transcript/Update:
        "{transcript}"

        Task: Update the chart. Follow the template structure strictly.
        Template:
        {chart_template}
        """

        # ADVISOR INPUT
        advisor_user_msg = f"""
        Patient Info: {patient.get('age_sex', 'Unknown')} - {patient.get('complaint', 'Unknown')}
        Transcript: "{transcript}"
        
        Task: Analyze this case. Give me the 'Wingman' perspective.
        """

        # 4. Run Sequential Inference (Fix for Metal/AGX Crash)
        # CRITICAL FIX: Replaced asyncio.gather with sequential awaits.
        # Running both agents concurrently causes a race condition on the Metal Command Encoder.
        logger.info(f"Running ER Agents for Patient {patient_id} (Sequential)...")
        
        # 4a. Run Scribe
        new_chart_content = await get_ai_response([
            {"role": "system", "content": scribe_prompt},
            {"role": "user", "content": scribe_user_msg}
        ])
        
        # Brief cooldown for Metal/GPU buffer to clear
        await asyncio.sleep(0.5)

        # 4b. Run Advisor
        advisor_analysis = await get_ai_response([
            {"role": "system", "content": advisor_prompt},
            {"role": "user", "content": advisor_user_msg}
        ])

        # 5. Save & Notify
        await save_er_chart(patient_id, new_chart_content, advisor_analysis)
        ER_STATUS[patient_id] = "Ready"
        logger.info(f"ER Update Complete for {patient_id}")

    except Exception as e:
        logger.error(f"ER Agent Failed: {e}", exc_info=True)
        ER_STATUS[patient_id] = "Error"