# backend/ingest_processors.py
import os
import json
import shutil
import base64
import logging
import asyncio
import aiofiles
import re
from datetime import date, datetime, timedelta
from dateutil.parser import parse as date_parse
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from icalendar import Calendar

import aiosqlite
from backend.database import get_all_settings, add_file_tag
from backend.config import (
    DOCS_PATH, STEWARD_JOURNAL_FOLDER, STEWARD_REMINDERS_FOLDER,
    STEWARD_INGEST_FOLDER, STEWARD_HEALTH_FOLDER, STEWARD_FINANCE_FOLDER,
    STEWARD_WEB_FOLDER, STEWARD_WORKOUT_FOLDER, STEWARD_NUTRITION_FOLDER,
    STEWARD_HOMESCHOOL_FOLDER, STEWARD_WORSHIP_FOLDER, STEWARD_MEALPLANS_FOLDER,
    SUPPORTED_EXTENSIONS, IMAGE_EXTENSIONS, STEWARD_CONTEXT_FOLDER
)
from backend.rag import get_ai_response, search_file
from backend.notifications import send_email

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

async def _extract_json_from_llm(llm_output: str, retry_prompt: str = None, retries: int = 1) -> Optional[Dict[str, Any]]:
    def clean_and_parse(text):
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        json_str = match.group(1) if match else ""
        if not json_str:
            s = text.find('{')
            e = text.rfind('}')
            if s != -1 and e != -1: json_str = text[s:e+1]
            else:
                s = text.find('[')
                e = text.rfind(']')
                if s != -1 and e != -1: json_str = text[s:e+1]
        try: return json.loads(json_str)
        except: return None

    data = clean_and_parse(llm_output)
    if data: return data

    if retries > 0:
        return None
    
    return None

def _parse_due_date(task_desc: str) -> Optional[datetime]:
    now = datetime.now()
    match = re.search(r'\b(by|due|on|tomorrow|next|in\s+\d+\s+(day|week|month|year)s?)\b.*', task_desc, re.IGNORECASE)
    if match:
        date_str = match.group(0).strip()
        if "tomorrow" in date_str.lower(): return now + timedelta(days=1)
        try:
            parsed_date = date_parse(date_str, default=now)
            if parsed_date.date() < now.date() and 'next' not in date_str.lower():
                parsed_date += relativedelta(weeks=1)
            return parsed_date
        except: return None
    return None

def _get_classification_config(choice: str) -> Tuple[str, str]:
    choice = choice.lower()
    if choice == 'diet': choice = 'nutrition'
    key = f"steward_{choice}_folder"
    
    if choice == "journal": return (key, STEWARD_JOURNAL_FOLDER)
    if choice == "reminders": return (key, STEWARD_REMINDERS_FOLDER)
    if choice == "context": return (key, STEWARD_CONTEXT_FOLDER)
    if choice == "health": return (key, STEWARD_HEALTH_FOLDER)
    if choice == "finance": return (key, STEWARD_FINANCE_FOLDER)
    if choice == "web": return (key, STEWARD_WEB_FOLDER)
    if choice == "workout": return (key, STEWARD_WORKOUT_FOLDER)
    if choice == "nutrition": return (key, STEWARD_NUTRITION_FOLDER)
    if choice == "homeschool": return (key, STEWARD_HOMESCHOOL_FOLDER)
    if choice == "worship": return (key, STEWARD_WORSHIP_FOLDER)
    if choice == "mealplan": return (key, STEWARD_MEALPLANS_FOLDER)
    
    return (key, "Vault_Documents")

# --- FILE INGESTORS ---
async def ingest_calendar_file(file_path: Path, conn: aiosqlite.Connection):
    try:
        async with aiofiles.open(file_path, 'rb') as f: content = await f.read()
        cal = Calendar.from_ical(content)
        cursor = await conn.cursor()
        for component in cal.walk():
            if component.name == "VEVENT":
                await cursor.execute("INSERT OR REPLACE INTO events (event_uid, start_time, end_time, title, source_file) VALUES (?,?,?,?,?)",
                    (str(component.get('uid')), component.get('dtstart').dt, component.get('dtend').dt, str(component.get('summary')), file_path.name))
        await conn.commit()
    except Exception: pass

# --- VOICE MEMO PROCESSORS ---
async def process_journal_memo(file_path: Path, conn: aiosqlite.Connection, settings: Dict[str, Any]):
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f: transcript = await f.read()
        folder = settings.get("steward_journal_folder", STEWARD_JOURNAL_FOLDER)
        target_path = DOCS_PATH / folder / datetime.now().strftime('%Y-%m-%d.md')
        target_path.parent.mkdir(exist_ok=True, parents=True)
        async with aiofiles.open(target_path, "a", encoding="utf-8") as f:
            await f.write(f"\n\n### Voice Journal @ {datetime.now().strftime('%H:%M:%S')}\n{transcript.strip()}\n")
        await asyncio.to_thread(os.remove, file_path)
    except Exception: pass

async def process_workout_memo(file_path: Path, conn: aiosqlite.Connection, ollama: Any, settings: Dict[str, Any]):
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f: transcript = await f.read()
        prompt = "Extract workout data as JSON list. Keys: exercise, sets, reps, weight, rpe."
        resp = await get_ai_response([{"role": "system", "content": prompt}, {"role": "user", "content": transcript}], model=settings.get("llm_model"))
        data = await _extract_json_from_llm(resp)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    await conn.execute("INSERT INTO workout_log (exercise, sets, reps, weight, rpe, source_tag, source_file) VALUES (?,?,?,?,?,?,?)",
                        (item.get("exercise"), item.get("sets"), str(item.get("reps")), item.get("weight"), item.get("rpe"), "WORKOUT", file_path.name))
            await conn.commit()
            await asyncio.to_thread(os.remove, file_path)
    except Exception: pass

async def process_nutrition_memo(file_path: Path, conn: aiosqlite.Connection, ollama: Any, settings: Dict[str, Any]):
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f: transcript = await f.read()
        prompt = "Estimate calories/macros. JSON keys: calories, protein, carbs, fat."
        resp = await get_ai_response([{"role": "system", "content": prompt}, {"role": "user", "content": transcript}], model=settings.get("llm_model"))
        data = await _extract_json_from_llm(resp)
        if isinstance(data, dict):
            await _upsert_nutrition(conn, data)
            await asyncio.to_thread(os.remove, file_path)
    except Exception: pass

async def process_meal_plan_memo(file_path: Path, conn: aiosqlite.Connection, ollama: Any, settings: Dict[str, Any]):
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f: pantry = await f.read()
        if not settings.get("recipient_email_family"): return
        docs, metas = await search_file(settings.get("steward_mealplans_folder", STEWARD_MEALPLANS_FOLDER), "all", "dietary preferences", k=5)
        prefs = "\n".join([m.get('window', d) for d, m in zip(docs, metas)])
        prompt = f"Create meal plan. Pantry:\n{pantry}\nPrefs:\n{prefs}"
        plan = await get_ai_response([{"role": "system", "content": settings.get("mealplan_generation_prompt")}, {"role": "user", "content": prompt}], model=settings.get("llm_model"))
        await send_email(f"Meal Plan - {date.today()}", plan, settings.get("recipient_email_family"))
        await asyncio.to_thread(os.remove, file_path)
    except Exception: pass

async def _upsert_nutrition(conn, data):
    today = date.today()
    async with conn.execute("SELECT * FROM daily_nutrition WHERE date = ?", (today,)) as cur: row = await cur.fetchone()
    current_cals = row["total_calories"] if row else 0
    current_prot = row["protein_g"] if row else 0
    vals = {
        "calories": current_cals + (data.get("calories") or 0),
        "protein": current_prot + (data.get("protein") or 0),
        "carbs": (row["carbs_g"] if row else 0) + (data.get("carbs") or 0),
        "fat": (row["fat_g"] if row else 0) + (data.get("fat") or 0)
    }
    await conn.execute("INSERT OR REPLACE INTO daily_nutrition (date, total_calories, protein_g, carbs_g, fat_g, source) VALUES (?,?,?,?,?,?)",
        (today, vals["calories"], vals["protein"], vals["carbs"], vals["fat"], "voice/vision"))
    await conn.commit()

async def process_mixed_image(file_path: Path, conn: aiosqlite.Connection, ollama: Any, settings: Dict[str, Any]):
    if not settings.get("vision_model"): return
    pass 

# --- CORE PROCESSING ---

async def classify_and_move_single(f: Path, conn: aiosqlite.Connection, settings: Dict[str, Any], targets: set, sem: asyncio.Semaphore):
    """Classifies a single file using LLM, bounded by semaphore."""
    async with sem:
        try:
            async with aiofiles.open(f, 'r', encoding='utf-8', errors='ignore') as r: snip = await r.read(500)
            
            prompt = f"""
            Analyze this document snippet. 
            1. Classify into: {', '.join(targets)}.
            2. Generate 3 tags.
            Format: "CATEGORY | #tag1 #tag2"
            """
            resp = await get_ai_response([{"role": "system", "content": prompt}, {"role": "user", "content": f"File: {f.name}\n{snip}"}], model=settings.get("llm_model"))
            
            parts = resp.split('|')
            choice = parts[0].strip().lower().replace('.','')
            tags = parts[1].strip() if len(parts) > 1 else ""
            
            if tags:
                for tag in tags.split():
                    if tag.startswith('#'): await add_file_tag(f.name, tag.strip())

            setting_key, default_folder = _get_classification_config(choice)
            folder_name = settings.get(setting_key)
            dest_folder_name = folder_name if folder_name else default_folder

            target_dir = DOCS_PATH / (dest_folder_name if dest_folder_name != "Vault_Documents" else "Vault_Documents")
            target_dir.mkdir(exist_ok=True, parents=True)
            
            await asyncio.to_thread(shutil.move, str(f), str(target_dir / f.name))
            print(f"  [MAGIC] ✨ {f.name} -> {target_dir.name}")

        except Exception as e:
            print(f"  [MAGIC] ❌ Error {f.name}: {e}")

async def process_ingest_folder(ollama: Any, conn: aiosqlite.Connection, settings: Dict[str, Any], ingest_folder: str, targets: set):
    path = DOCS_PATH / ingest_folder
    if not path.exists(): return
    
    # 1. Pre-filter Files
    files_to_process = []
    files_to_classify = []
    
    tag_map = {"REMINDER": "steward_reminders_folder", "CONTEXT": "steward_context_folder", "FINANCE": "steward_finance_folder"}
    
    for f in path.iterdir():
        if not f.is_file() or f.name.startswith('.'): continue
        if f.suffix.lower() not in SUPPORTED_EXTENSIONS and f.suffix.lower() not in IMAGE_EXTENSIONS: continue
        
        match = re.search(r"_TAG-([A-Z]+)\.", f.name)
        if match:
            files_to_process.append((f, match.group(1).upper()))
        elif f.suffix.lower() in IMAGE_EXTENSIONS:
            files_to_process.append((f, "IMAGE"))
        else:
            files_to_classify.append(f)

    # 2. Handle Tagged Files
    for f, tag in files_to_process:
        if tag == "JOURNAL": await process_journal_memo(f, conn, settings)
        elif tag == "WORKOUT": await process_workout_memo(f, conn, ollama, settings)
        elif tag == "DIET": await process_nutrition_memo(f, conn, ollama, settings)
        elif tag == "MEALPLAN": await process_meal_plan_memo(f, conn, ollama, settings)
        elif tag == "IMAGE": await process_mixed_image(f, conn, ollama, settings)
        elif tag in tag_map:
             dest = DOCS_PATH / settings.get(tag_map[tag], "Vault_Documents")
             dest.mkdir(exist_ok=True, parents=True)
             shutil.move(str(f), str(dest / f.name))

    # 3. Parallel Classification
    if files_to_classify:
        print(f"  [MAGIC] Classifying {len(files_to_classify)} files...")
        # CRITICAL FIX: Changed from 4 to 1. Local LLM cannot run in parallel.
        sem = asyncio.Semaphore(1) 
        await asyncio.gather(*[classify_and_move_single(f, conn, settings, targets, sem) for f in files_to_classify])