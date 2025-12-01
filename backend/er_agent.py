import asyncio
import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from backend.database import (
    get_latest_er_chart, update_er_chart, 
    get_er_patient, get_all_settings,
    get_medical_sources
)
from backend.rag import (
    get_ai_response, search_file
)
from backend.web_search import perform_medical_search
from backend.notifications import send_clinical_notification
from backend.config import STEWARD_MEDICAL_FOLDER, sanitize_collection_name

logger = logging.getLogger(__name__)

# GLOBAL STATUS TRACKER
ER_STATUS: Dict[int, str] = {}

# ============================================================================
# ENHANCED SYSTEM PROMPTS
# ============================================================================

SCRIBE_SYSTEM_PROMPT = """You are an expert Emergency Medicine clinical scribe AI.
YOUR ROLE: Transform physician dictations into structured, professional EM documentation.

CRITICAL RULES:
1. NEVER invent or assume information not stated in the dictation
2. Update existing sections seamlessly - integrate new info into narrative
3. Use standard EM note format (HPI, PMH, Meds, Allergies, Physical Exam, ED Course, Labs/Imaging, Assessment/Plan)
4. Write HPI in past tense, third person, chronological narrative
5. Include relevant negatives when mentioned
6. Mark incomplete sections as [PENDING]
7. For conflicting information, flag as [CONFLICT: old vs new - needs clarification]

HPI STRUCTURE (Use OLDCARTS when applicable):
- Onset: When did it start? What was patient doing?
- Location: Where is the symptom?
- Duration: How long has it lasted?
- Character: What does it feel like? (sharp, dull, pressure, etc.)
- Aggravating/Alleviating factors
- Radiation: Does it spread anywhere?
- Timing: Constant vs intermittent? Getting better/worse?
- Severity: Pain scale, functional impact

PHYSICAL EXAM RULES:
- Only document what was explicitly examined
- Use standard format: General, Vitals, HEENT, Neck, Lungs, CV, Abdomen, Extremities, Neuro, Skin
- If abnormal finding mentioned, describe it precisely
- Include pertinent negatives (e.g., "No rales, wheezes, or rhonchi")

ED COURSE:
- Time-stamp all interventions and events
- Document medications given (drug, dose, route, time)
- Record diagnostic test orders and results
- Note patient's response to treatments

OUTPUT FORMAT:
Return the complete updated chart in the template structure provided.
Keep language concise and professional."""

ADVISOR_SYSTEM_PROMPT = """You are a senior Emergency Medicine attending physician providing clinical decision support.
YOUR ROLE: Analyze the complete clinical picture and provide evidence-based guidance.

CRITICAL MANDATE:
- Be PROACTIVE: Don't wait to be asked
- Be SPECIFIC: Give exact doses, timing, test names
- Be EVIDENCE-BASED: Cite guidelines when available
- Be SAFETY-FOCUSED: Flag dangerous patterns immediately
- Think about "Can't Miss" diagnoses first

COGNITIVE FRAMEWORK:
1. What are the life threats? (ABC problems, time-sensitive diagnoses)
2. What dangerous diagnoses CANNOT be missed given this presentation?
3. Does the current workup adequately rule these out?
4. What cognitive biases might be occurring? (Anchoring, premature closure, availability bias)

RESPONSE STRUCTURE:
You MUST return a valid JSON object with exactly these fields:
{
  "critical_alerts": [
    {
      "alert": "Brief description of the critical issue",
      "severity": "CRITICAL" | "URGENT" | "IMPORTANT",
      "action_required": "Specific action needed now",
      "time_sensitive": true/false,
      "evidence": "Source/guideline if applicable"
    }
  ],
  "differential_diagnosis": [
    {
      "diagnosis": "Diagnosis name",
      "probability": 1-100,
      "status": "CONFIRMED" | "LIKELY" | "POSSIBLE" | "RULED_OUT",
      "cant_miss": true/false,
      "supporting_evidence": ["List of supporting findings"],
      "contradicting_evidence": ["List of contradicting findings"]
    }
  ],
  "diagnostic_plan": [
    {
      "test": "Test name",
      "priority": "IMMEDIATE" | "URGENT" | "ROUTINE" | "DEFERRED",
      "rationale": "Why this test is needed",
      "status": "PENDING" | "COMPLETED" | "NOT_INDICATED"
    }
  ],
  "treatment_recommendations": [
    {
      "intervention": "Treatment/medication name",
      "dose": "Specific dosing (include weight-based if needed)",
      "priority": "IMMEDIATE" | "URGENT" | "ROUTINE",
      "contraindications_checked": ["List relevant contraindications ruled out"],
      "evidence": "Guideline or study reference"
    }
  ],
  "disposition_guidance": {
    "recommendation": "ADMIT" | "OBSERVATION" | "DISCHARGE" | "TRANSFER",
    "service": "Service to admit to (if applicable)",
    "level_of_care": "ICU" | "Telemetry" | "Floor" | null,
    "reasoning": "Brief explanation",
    "discharge_criteria": "If discharge, what criteria were met?",
    "return_precautions": "Specific symptoms requiring return"
  },
  "cognitive_bias_check": [
    {
      "bias_type": "ANCHORING" | "PREMATURE_CLOSURE" | "AVAILABILITY" | "CONFIRMATION",
      "concern": "Description of the bias risk",
      "alternative_consideration": "What else to consider"
    }
  ],
  "metadata": {
    "confidence_overall": "HIGH" | "MODERATE" | "LOW",
    "data_completeness": 0.0-1.0,
    "key_missing_data": ["List critical missing information"]
  }
}

RETURN ONLY VALID JSON. No markdown, no explanation, just the JSON object."""

DEFAULT_CHART_TEMPLATE = """# Emergency Department Chart
## HPI
[PENDING]

## Past Medical History
[PENDING]

## Medications
[PENDING]

## Allergies
[PENDING]

## Social History
[PENDING]

## Review of Systems
[PENDING]

## Physical Examination
General: [PENDING]
Vitals: [PENDING]
HEENT: [PENDING]
Neck: [PENDING]
Cardiovascular: [PENDING]
Respiratory: [PENDING]
Abdomen: [PENDING]
Extremities: [PENDING]
Neurological: [PENDING]
Skin: [PENDING]

## ED Course
[PENDING]

## Laboratory & Imaging Results
[PENDING]

## Assessment & Plan
[PENDING]

## Medical Decision Making
[PENDING]"""

# ============================================================================
# CLINICAL CONTEXT & CHANGE DETECTION
# ============================================================================

class ClinicalContext:
    """Maintains state and detects meaningful changes between updates"""
    
    def __init__(self, previous_chart: str, previous_guidance: Optional[Dict]):
        self.previous_chart = previous_chart
        self.previous_guidance = previous_guidance or {}
        
    def extract_vitals(self, text: str) -> Dict:
        """Extract vital signs from text"""
        vitals = {}
        bp_match = re.search(r'BP:?\s*(\d{2,3})/(\d{2,3})', text)
        hr_match = re.search(r'HR:?\s*(\d{2,3})', text)
        rr_match = re.search(r'RR:?\s*(\d{1,2})', text)
        temp_match = re.search(r'Temp:?\s*(\d{2,3}\.?\d*)', text)
        o2_match = re.search(r'(?:SpO2|O2):?\s*(\d{2,3})%?', text)
        
        if bp_match:
            vitals['bp_systolic'] = int(bp_match.group(1))
            vitals['bp_diastolic'] = int(bp_match.group(2))
        if hr_match: vitals['heart_rate'] = int(hr_match.group(1))
        if rr_match: vitals['respiratory_rate'] = int(rr_match.group(1))
        if temp_match: vitals['temperature'] = float(temp_match.group(1))
        if o2_match: vitals['oxygen_sat'] = int(o2_match.group(1))
            
        return vitals
        
    def detect_critical_changes(self, new_chart: str) -> List[str]:
        """Detect clinically significant changes"""
        changes = []
        old_vitals = self.extract_vitals(self.previous_chart)
        new_vitals = self.extract_vitals(new_chart)
        
        # Critical vital changes
        if new_vitals.get('bp_systolic', 0) > 180 and old_vitals.get('bp_systolic', 0) <= 180:
            changes.append("NEW_CRITICAL_HTN")
        if new_vitals.get('oxygen_sat', 100) < 90 and old_vitals.get('oxygen_sat', 100) >= 90:
            changes.append("NEW_HYPOXIA")
        if new_vitals.get('heart_rate', 0) > 120 and old_vitals.get('heart_rate', 0) <= 120:
            changes.append("NEW_TACHYCARDIA")
            
        return changes

    def should_regenerate_guidance(self, new_transcript: str) -> bool:
        """Determine if new guidance generation is needed"""
        # Always check for critical keywords in new dictation
        clinical_keywords = [
            'pain', 'troponin', 'ECG', 'CT', 'xray', 'ultrasound',
            'worsening', 'improving', 'medication', 'response to',
            'admit', 'discharge', 'consult', 'labs'
        ]
        if any(keyword in new_transcript.lower() for keyword in clinical_keywords):
            return True
            
        # Check if the transcription is substantial (> 10 words)
        if len(new_transcript.split()) > 10:
            return True
            
        return False

# ============================================================================
# RAG QUERY GENERATION
# ============================================================================

def generate_hypothesis_queries(patient_data: Dict, differentials: List[str]) -> List[str]:
    """Generate targeted medical literature queries"""
    
    age = patient_data.get('age_sex', '')
    complaint = patient_data.get('chief_complaint', '')
    
    queries = []
    
    # Scenario-specific templates
    scenario_templates = {
        'chest pain': [
            f"HEART score validation {age}",
            "chest pain risk stratification emergency department 2024",
            "acute coronary syndrome diagnosis guidelines"
        ],
        'abdominal pain': [
            f"abdominal pain {age} emergency evaluation",
            "acute abdomen imaging guidelines",
            "appendicitis clinical decision rules"
        ],
        'shortness of breath': [
            "dyspnea emergency department workup 2024",
            "pulmonary embolism PERC rule Wells score",
            "heart failure BNP cutoff emergency"
        ],
        'altered mental status': [
            f"altered mental status {age} differential",
            "delirium workup emergency department",
            "stroke NIHSS emergency guidelines"
        ],
        'sepsis': [
            "sepsis emergency department antibiotics 2024",
            "qSOFA score validation",
            "surviving sepsis campaign guidelines"
        ]
    }
    
    # Match complaint to scenario
    found_template = False
    for scenario, templates in scenario_templates.items():
        if scenario in complaint.lower():
            queries.extend(templates[:2])
            found_template = True
            break
            
    # Fallback if no template matches
    if not found_template:
        queries.append(f"{complaint} emergency medicine guidelines workup")

    # Add differential-specific queries
    for diff in differentials[:3]:  # Top 3 differentials
        queries.append(f"{diff} emergency medicine diagnosis 2024")
        
    # Deduplicate and limit
    return list(dict.fromkeys(queries))[:5]

# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

async def process_er_audio_update(patient_id: int, transcript: str):
    """
    Enhanced Clinical Agent with Scribe/Advisor separation and sequential processing
    to prevent local LLM segfaults.
    """
    logger.info(f"Processing ER update for PID {patient_id}")
    ER_STATUS[patient_id] = "Processing transcript..."
    
    try:
        settings = await get_all_settings()
        model = settings.get("llm_model", "phi4-mini")
        
        # Load custom prompts if available
        scribe_prompt = settings.get("er_system_scribe", SCRIBE_SYSTEM_PROMPT)
        advisor_prompt = settings.get("er_system_attending", ADVISOR_SYSTEM_PROMPT)
        master_template = settings.get("er_master_chart_template", DEFAULT_CHART_TEMPLATE)

        # 1. FETCH CONTEXT
        patient = await get_er_patient(patient_id)
        if not patient:
            logger.error(f"Patient {patient_id} not found")
            return

        last_chart_row = await get_latest_er_chart(patient_id)
        current_chart = last_chart_row['chart_markdown'] if last_chart_row else master_template
        
        # Get previous guidance
        previous_guidance = None
        if last_chart_row and last_chart_row.get('clinical_guidance_json'):
            try:
                previous_guidance = json.loads(last_chart_row['clinical_guidance_json'])
            except: pass
            
        context = ClinicalContext(current_chart, previous_guidance)

        # 2. STEP: SCRIBE (Update Documentation)
        ER_STATUS[patient_id] = "Updating chart..."
        
        scribe_user_prompt = f"""Update the emergency department chart with the new dictation.
CURRENT CHART:
{current_chart}

NEW DICTATION:
"{transcript}"

INSTRUCTIONS:
- Integrate new information seamlessly into existing sections
- If this is new history, update HPI section
- If physical exam findings, update Physical Examination
- If orders or results, update ED Course and Labs/Results
- If assessment/plan, update Assessment & Plan
- Maintain chronological flow in narratives
- Flag any conflicts with [CONFLICT: ... ]
- Keep professional medical documentation style

Return the COMPLETE updated chart."""
        
        updated_chart = await get_ai_response([
            {"role": "system", "content": scribe_prompt},
            {"role": "user", "content": scribe_user_prompt}
        ], model=model)

        # 3. STEP: ANALYZE PROBLEMS
        ER_STATUS[patient_id] = "Analyzing clinical problems..."
        
        problem_prompt = f"""Analyze this emergency department case and identify the top 1-3 active clinical problems that need immediate attention.
PATIENT:
- Demographics: {patient['age_sex']}
- Chief Complaint: {patient['chief_complaint']}
- Room: {patient['room_label']}

LATEST UPDATE:
"{transcript}"

Return ONLY a JSON array of problem strings, e.g.:
["Acute Coronary Syndrome", "Hypertensive Emergency"]"""
        
        try:
            problems_json = await get_ai_response([{"role": "user", "content": problem_prompt}], model=model)
            # Robust cleaning
            problems_json = problems_json.strip()
            if "```json" in problems_json: problems_json = problems_json.split("```json")[1].split("```")[0]
            elif "```" in problems_json: problems_json = problems_json.split("```")[1]
            
            active_problems = json.loads(problems_json)
            if not isinstance(active_problems, list): active_problems = [patient['chief_complaint']]
        except:
            active_problems = [patient['chief_complaint']]

        # 4. RAG RESEARCH & ADVISOR
        clinical_guidance = previous_guidance
        
        if context.should_regenerate_guidance(transcript):
            ER_STATUS[patient_id] = "Consulting medical literature..."
            
            queries = generate_hypothesis_queries(patient, active_problems)
            research_findings = []
            
            sources = await get_medical_sources()
            approved_sites = [s['url_pattern'] for s in sources] if sources else []
            
            # Execute Search for top problems
            # Use Sanitized Name from Config to ensure match with Ingest
            med_collection = sanitize_collection_name(STEWARD_MEDICAL_FOLDER)
            
            for problem in active_problems[:2]:
                finding = f"=== {problem} ===\n"
                
                # RAG Search (Local)
                try:
                    docs, metas = await search_file(med_collection, "all", f"{problem} guidelines", k=2)
                    if docs: finding += f"CLINICAL GUIDELINES:\n{docs[0][:500]}\n\n"
                except: pass
                
                # Web Search (External)
                if approved_sites:
                    try:
                        web_result = await perform_medical_search(
                            f"{problem} emergency medicine guidelines 2024",
                            model,
                            sites=approved_sites
                        )
                        finding += f"EVIDENCE:\n{web_result[:500]}\n"
                    except: pass
                
                research_findings.append(finding)
            
            research_context = "\n\n".join(research_findings)

            # 5. CLINICAL ADVISOR (The Synthesis)
            ER_STATUS[patient_id] = "Generating clinical guidance..."
            
            advisor_user_prompt = f"""You are supervising this Emergency Department case. Provide comprehensive clinical decision support.

PATIENT INFORMATION:
- Age/Sex: {patient['age_sex']}
- Chief Complaint: {patient['chief_complaint']}
- Room: {patient['room_label']}
- Arrival Time: {patient['created_at']}

COMPLETE MEDICAL RECORD:
{updated_chart}

LATEST CLINICAL UPDATE:
"{transcript}"

ACTIVE CLINICAL PROBLEMS:
{json.dumps(active_problems, indent=2)}

RELEVANT EVIDENCE & GUIDELINES:
{research_context}

PREVIOUS GUIDANCE (for comparison):
{json.dumps(previous_guidance, indent=2) if previous_guidance else "None - this is initial assessment"}

---
Provide your clinical decision support in the exact JSON format specified in your system prompt.
Focus on:
1. What are the immediate life threats?
2. What dangerous diagnoses cannot be missed?
3. Is the current workup adequate?
4. What specific actions should happen next?

Return ONLY the JSON object."""

            advisor_response = await get_ai_response([
                {"role": "system", "content": advisor_prompt},
                {"role": "user", "content": advisor_user_prompt}
            ], model=model)
            
            try:
                # Robust JSON Parsing
                clean_json = advisor_response.strip()
                if '```json' in clean_json:
                    clean_json = clean_json.split('```json')[1].split('```')[0]
                elif '```' in clean_json:
                    clean_json = clean_json.split('```')[1]
                
                clinical_guidance = json.loads(clean_json)
                
                # Metadata
                clinical_guidance['metadata'] = clinical_guidance.get('metadata', {})
                clinical_guidance['metadata']['last_updated'] = datetime.now().isoformat()
                
            except Exception as e:
                logger.error(f"Advisor JSON parse failed: {e}")
                # FALLBACK: Minimal valid object to prevent UI breakage
                clinical_guidance = {
                    "critical_alerts": [{"alert": "Review chart manually - AI analysis failed", "severity": "IMPORTANT", "action_required": "Review", "time_sensitive": False}],
                    "differential_diagnosis": [{"diagnosis": p, "probability": 50, "status": "POSSIBLE", "cant_miss": True, "supporting_evidence": [], "contradicting_evidence": []} for p in active_problems],
                    "diagnostic_plan": [],
                    "treatment_recommendations": [],
                    "disposition_guidance": {"recommendation": "OBSERVATION", "reasoning": "Pending full analysis"},
                    "cognitive_bias_check": []
                }

        # 6. SAVE
        ER_STATUS[patient_id] = "Finalizing..."
        
        # Legacy fields for backward compatibility
        differentials = []
        if clinical_guidance and 'differential_diagnosis' in clinical_guidance:
            differentials = [d.get('diagnosis') for d in clinical_guidance['differential_diagnosis']]
            
        pearls = []
        if clinical_guidance and 'critical_alerts' in clinical_guidance:
            pearls = [a.get('alert') for a in clinical_guidance['critical_alerts']]
            
        scratchpad = []
        if clinical_guidance and 'cognitive_bias_check' in clinical_guidance:
            scratchpad = [b.get('concern') for b in clinical_guidance['cognitive_bias_check']]

        await update_er_chart(
            pid=patient_id,
            chart_md=updated_chart,
            scratchpad=json.dumps(scratchpad),
            transcript=transcript,
            pearls=json.dumps(pearls),
            diffs=json.dumps(differentials),
            clinical_guidance_json=json.dumps(clinical_guidance) if clinical_guidance else None,
            guidance_version=1
        )

        # 7. NOTIFY
        if clinical_guidance and clinical_guidance.get('critical_alerts'):
            # Count criticals
            crits = [a for a in clinical_guidance['critical_alerts'] if a.get('severity') == 'CRITICAL']
            if crits:
                alert_text = crits[0]['alert']
                await send_clinical_notification("CRITICAL ALERT", f"🚨 {patient['room_label']}: {alert_text}")
            else:
                await send_clinical_notification("Clinical Update", f"{patient['room_label']}: Chart updated.")
        else:
            await send_clinical_notification("Clinical Update", f"{patient['room_label']}: Chart updated.")

    except Exception as e:
        logger.error(f"Error in process_er_audio_update: {e}", exc_info=True)
    finally:
        if patient_id in ER_STATUS: del ER_STATUS[patient_id]
        logger.info(f"ER Update Complete for PID {patient_id}")