# backend/er_agent.py
import logging
import asyncio
import json
import re
from typing import Dict, List, Any

from backend.database import get_all_settings
from backend.er_db import save_er_chart, get_er_patient_data
from backend.rag import get_ai_response, perform_rag_query
from backend.email_tools import send_clinical_alert
from backend.prompts import (
    SCRIBE_SYSTEM_PROMPT, 
    ADVISOR_SYSTEM_PROMPT, 
    DEFAULT_CHART_TEMPLATE
)

logger = logging.getLogger(__name__)

ER_STATUS: Dict[int, str] = {}

def extract_json(text: str) -> str:
    """Extracts JSON block from text if wrapped in markdown."""
    try:
        # Find matches for ```json ... ```
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match: return match.group(1)
        
        # Fallback: Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        
        return text
    except: return text

async def process_er_audio_update(patient_id: int, transcript: str):
    """
    Orchestrates the Clinical Loop:
    1. Fetch Patient + History
    2. RAG Search (Emergency Medicine Guidelines)
    3. Scribe Agent (Write Note)
    4. Attending Agent (Clinical Feedback)
    5. Save & Email
    """
    
    ER_STATUS[patient_id] = "Processing..."
    
    try:
        # 1. Fetch Context & History
        patient = await get_er_patient_data(patient_id)
        if not patient:
            logger.error(f"Patient {patient_id} not found.")
            ER_STATUS[patient_id] = "Error: Not Found"
            return

        current_chart = patient.get("chart_content", "") or ""
        dictation_history = patient.get("dictation_history", [])
        recommendation_history = patient.get("recommendation_history", [])
        
        # Add new dictation to history (for prompt context)
        dictation_history.append({"timestamp": str(asyncio.get_running_loop().time()), "content": transcript})
        
        # 2. RAG Search (Standards of Care)
        # Search the "Emergency Medicine" folder for context relevant to the transcript
        logger.info(f"🔍 RAG Search for Patient {patient_id}...")
        rag_docs, _ = await perform_rag_query(transcript, folder="Emergency Medicine", file="all")
        rag_context = "\\n\\n".join(rag_docs[:3]) if rag_docs else "No specific guidelines found."

        # 3. Get Settings
        settings = await get_all_settings()
        scribe_prompt = settings.get("er_scribe_prompt", SCRIBE_SYSTEM_PROMPT)
        advisor_prompt = settings.get("er_advisor_prompt", ADVISOR_SYSTEM_PROMPT)
        chart_template = settings.get("er_chart_template", DEFAULT_CHART_TEMPLATE)

        # 4. Construct Prompts (FULL CONTEXT)
        
        # SCRIBE INPUT (Needs history to maintain flow)
        scribe_user_msg = f"""
        === PATIENT DATA ===
        Age/Sex: {patient.get('age_sex', 'Unknown')}
        CC: {patient.get('complaint', 'Unknown')}
        
        === CURRENT CHART STATE ===
        {current_chart if current_chart else "[New Patient]"}

        === NEW DICTATION ===
        "{transcript}"

        === TASK ===
        Update the chart based on the new dictation. Maintain the existing structure.
        Template:
        {chart_template}
        """

        # ADVISOR INPUT (Needs EVERYTHING)
        advisor_user_msg = f"""
        === CASE CONTEXT ===
        Patient: {patient.get('age_sex', 'Unknown')} | {patient.get('complaint', 'Unknown')}
        
        === DICTATION HISTORY (Chronological) ===
        {json.dumps([d['content'] for d in dictation_history], indent=2)}
        
        === CURRENT CHART ===
        {current_chart}
        
        === RAG GUIDELINES / STANDARDS FOUND ===
        {rag_context}
        
        === PAST RECOMMENDATIONS ===
        {json.dumps(recommendation_history, indent=2)}
        
        === YOUR TASK ===
        Analyze the *new* information in the context of the *whole* case. 
        Provide critical decision support, medication doses, and safety checks in valid JSON.
        """

        # 5. Run Sequential Inference
        logger.info(f"🤖 Running ER Agents for Patient {patient_id}...")
        
        # 5a. Run Scribe
        new_chart_content = await get_ai_response([
            {"role": "system", "content": scribe_prompt},
            {"role": "user", "content": scribe_user_msg}
        ])
        
        await asyncio.sleep(0.5) # Metal Cooldown

        # 5b. Run Advisor (Attending Physician)
        raw_advisor_json = await get_ai_response([
            {"role": "system", "content": advisor_prompt},
            {"role": "user", "content": advisor_user_msg}
        ])
        
        # Clean & Validate JSON
        clean_json_str = extract_json(raw_advisor_json)
        try:
            advisor_data = json.loads(clean_json_str)
            # Add to history
            recommendation_history.append(advisor_data)
        except json.JSONDecodeError:
            logger.error("❌ Advisor output was not valid JSON.")
            advisor_data = {"error": "Invalid JSON output from Advisor"}
            clean_json_str = json.dumps(advisor_data)

        # 6. Save Everything
        await save_er_chart(
            patient_id, 
            new_chart_content, 
            clean_json_str, # Save as string for frontend
            dictation_history, 
            recommendation_history
        )
        
        # 7. Email Notification
        email_content = f"""
        <b>Patient:</b> {patient.get('age_sex')} - {patient.get('complaint')}<br>
        <b>Latest Update:</b> "{transcript}"<br>
        <hr>
        <b>👨‍⚕️ ATTENDING FEEDBACK:</b><br>
        <pre>{json.dumps(advisor_data, indent=2)}</pre>
        """
        
        asyncio.create_task(send_clinical_alert(
            to_email="alsupc@icloud.com",
            subject=f"ER CONSUL: {patient.get('room', 'ER')} - {patient.get('complaint')}",
            content=email_content
        ))

        ER_STATUS[patient_id] = "Ready"
        logger.info(f"✅ ER Update Complete for {patient_id}")

    except Exception as e:
        logger.error(f"❌ ER Agent Failed: {e}", exc_info=True)
        ER_STATUS[patient_id] = "Error"