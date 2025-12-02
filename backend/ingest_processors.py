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
from backend.tts import get_whisper_model # <--- Centralized Loader

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

# --- MEDIA HANDLERS ---

async def transcribe_audio_file(file_path: Path):
    """Transcribes an audio file using the centralized Whisper model."""
    model = await get_whisper_model()
    if not model:
        print("  [MAGIC] ❌ Whisper model unavailable.")
        return None

    try:
        def _transcribe():
            # The wrapper we built in tts.py now handles the model path automatically
            return model.transcribe(str(file_path))
        
        res = await asyncio.to_thread(_transcribe)
        return res.get("text", "").strip()
    except Exception as e:
        print(f"Transcription failed for {file_path}: {e}")
        return None

async def extract_pdf_text(file_path: Path) -> str:
    """Extracts text from PDF using pypdf if available, else simplistic extraction."""
    try:
        import pypdf
        def _read():
            reader = pypdf.PdfReader(file_path)
            full_text = []
            for page in reader.pages:
                full_text.append(page.extract_text())
            return "\n".join(full_text)
        
        text = await asyncio.to_thread(_read)
        return text
    except ImportError:
        return "[PDF Content - Install pypdf for extraction]"
    except Exception as e:
        return f"[PDF Error: {e}]"

# --- CORE PROCESSING ---

async def classify_and_move_single(f: Path, conn: aiosqlite.Connection, settings: Dict[str, Any], targets: set, sem: asyncio.Semaphore):
    """Classifies a single file using LLM, bounded by semaphore."""
    async with sem:
        try:
            # READ CONTENT (Handle Text, Audio, PDF)
            content_to_analyze = ""
            is_media_converted = False
            
            # 1. TEXT FILES
            if f.suffix.lower() in ['.txt', '.md', '.json', '.csv']:
                async with aiofiles.open(f, 'r', encoding='utf-8', errors='ignore') as r: 
                    content_to_analyze = await r.read(1000)

            # 2. AUDIO FILES (Magic Transcribe)
            elif f.suffix.lower() in ['.mp3', '.wav', '.m4a', '.webm', '.ogg']:
                print(f"  [MAGIC] 🎙️ Transcribing {f.name}...")
                transcript = await transcribe_audio_file(f)
                if transcript:
                    content_to_analyze = transcript
                    is_media_converted = True
                    # Replace audio file with text file
                    new_path = f.with_suffix('.txt')
                    async with aiofiles.open(new_path, 'w', encoding='utf-8') as w:
                        await w.write(f"Transcribed from {f.name}:\n\n{transcript}")
                    # Delete original audio
                    await asyncio.to_thread(os.remove, f)
                    f = new_path # Point to new text file for moving

            # 3. PDF FILES (Magic OCR/Extract)
            elif f.suffix.lower() == '.pdf':
                print(f"  [MAGIC] 📄 Extracting PDF {f.name}...")
                pdf_text = await extract_pdf_text(f)
                if pdf_text and len(pdf_text) > 10:
                    content_to_analyze = pdf_text[:1000]
            
            if not content_to_analyze:
                return

            prompt = f"""
            Analyze this document snippet. 
            1. Classify into: {', '.join(targets)}.
            2. Generate 3 tags.
            Format: "CATEGORY | #tag1 #tag2"
            """
            resp = await get_ai_response([{"role": "system", "content": prompt}, {"role": "user", "content": f"File: {f.name}\n{content_to_analyze}"}], model=settings.get("llm_model"))
            
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
    files_to_classify = []
    
    for f in path.iterdir():
        if not f.is_file() or f.name.startswith('.'): continue
        if f.suffix.lower() not in SUPPORTED_EXTENSIONS and f.suffix.lower() not in IMAGE_EXTENSIONS: continue
        
        files_to_classify.append(f)

    # 2. Parallel Classification
    if files_to_classify:
        print(f"  [MAGIC] Processing {len(files_to_classify)} items in Inbox...")
        # Use semaphore to limit concurrency
        sem = asyncio.Semaphore(1) 
        await asyncio.gather(*[classify_and_move_single(f, conn, settings, targets, sem) for f in files_to_classify])