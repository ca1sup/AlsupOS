# Force Tokenizers to run sequentially to prevent Metal/Fork crashes on macOS
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from fastapi import (
    FastAPI, WebSocket, HTTPException, WebSocketDisconnect,
    UploadFile, File, Request, BackgroundTasks
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import sys
import asyncio
import io
import zipfile
import tempfile
import shutil
import logging
from contextlib import asynccontextmanager
from multiprocessing import Process, Queue

# Internal Imports
from backend.immich import search_immich_photos 
from backend.interpreter import run_python_code 
from logging.handlers import RotatingFileHandler
from pathlib import Path
from starlette.responses import (
    FileResponse, HTMLResponse, StreamingResponse, Response
)
from pydantic import BaseModel
from datetime import datetime
import re
import aiofiles
from typing import Optional

# --- SCHEDULER & EVENT LOOP ---
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError: pass

from apscheduler.schedulers.asyncio import AsyncIOScheduler 

from backend.steward_job import run_daily_summary
from backend.apple_actions import add_reminder_to_app, run_apple_reminders_sync 
from backend.finance_sync import run_finance_sync, get_finance_structured
from backend.med_news import run_med_news_sync
from backend.email_ingest import run_email_ingest
from backend.memory import extract_and_store_fact
from backend.calendar_sync import run_calendar_sync
from backend.web_search import perform_web_search 
from backend.agent import agent_stream
from backend.er_agent import process_er_audio_update, ER_STATUS

# Ingest Worker Import
from backend.ingest import run_ingest_process

try:
    from backend.tts import generate_audio_briefing
except ImportError:
    async def generate_audio_briefing(text): return ""

from backend.email_tools import create_draft_task
from backend.analysis import get_mood_health_correlation
from chromadb import PersistentClient

from backend.config import (
    MANIFEST_PATH, FRONTEND_PATH, BASE_DIR,
    DB_STEWARD_PATH, DOCS_PATH, DB_PATH,
    sanitize_collection_name,
    UPLOAD_CHUNK_SIZE,
    WS_RECEIVE_TIMEOUT,
    WS_HEARTBEAT_INTERVAL,
    DEFAULT_SEARCH_K,
    STEWARD_REMINDERS_FOLDER,
    STEWARD_JOURNAL_FOLDER,
    STEWARD_INGEST_FOLDER,
    STEWARD_HEALTH_FOLDER,
    BACKUP_PATH, LOGS_PATH,
    MEDICAL_SPEECH_PROMPT,
    MODELS_DIR,          
    DEFAULT_MLX_MODEL    
)
from backend.rag import (
    search_file, generate_stream, generate_bare_stream,
    get_document_content,
    get_whoosh_index, perform_rag_query,
    init_llm,
    check_ollama_status
)
from backend.rag import load_settings as load_rag_settings

from backend.database import (
    get_db_connection,
    add_chat_message,
    get_latest_suggestion, get_pending_tasks, get_weeks_events_structured,
    update_task_status,
    prune_old_chat_sessions,
    get_recent_journals_structured,
    get_journal_memories,
    get_recent_health_metrics_structured,
    get_all_user_facts,
    get_all_user_facts_structured,
    delete_user_fact,
    get_personas, 
    update_persona, 
    delete_persona,
    get_sentiment_history,
    create_er_patient, get_active_er_patients, get_latest_er_chart,
    archive_er_patient, delete_er_patient,
    get_medical_sources, add_medical_source, delete_medical_source,
    init_db, get_sessions, create_session, delete_session,
    get_chat_history, get_folders, get_files_in_folder,
    get_er_dashboard_data, get_er_chart,
    get_all_settings, update_settings, update_session_name as update_chat_session_name
)

# --- LOGGING SETUP ---
if not LOGS_PATH.exists(): LOGS_PATH.mkdir(parents=True)
log_file = LOGS_PATH / "steward.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- WHISPER & MLX SETUP ---
try:
    import whisper
    WHISPER_MODEL = None # Global Model Instance
except ImportError:
    whisper = None
    logger.warning("Whisper library not installed. Voice features disabled.")

# --- GLOBAL INGEST STATE ---
ingest_process: Optional[Process] = None
ingest_status_queue: Optional[Queue] = None

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP
    logger.info("⚡ Steward Backend Starting...")
    await init_db()
    await load_rag_settings()
    
    # Init MLX LLM (Chat Model)
    asyncio.create_task(init_llm())

    # Pre-load Whisper Model (Prevents SegFaults during runtime)
    global WHISPER_MODEL
    if whisper:
        try:
            logger.info("Loading Whisper model (small.en)...")
            WHISPER_MODEL = whisper.load_model("small.en")
            logger.info("✅ Whisper Model Loaded.")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")

    # Start Scheduler
    try:
        settings = await get_all_settings()
        job_time = settings.get("steward_job_time", "06:00").split(":")
        
        scheduler.add_job(run_daily_summary, trigger='cron', hour=int(job_time[0]), minute=int(job_time[1]))
        scheduler.add_job(run_backup_job, trigger='cron', hour=4, minute=0)
        scheduler.add_job(prune_old_chat_sessions, trigger='cron', day_of_week='sun', hour=3, minute=0)
        
        # New Scheduled Ingest Check (Checks if process is running)
        scheduler.add_job(scheduled_ingest_check, trigger='interval', minutes=10)
        
        scheduler.add_job(run_finance_sync, trigger='cron', hour=1, minute=0)
        scheduler.add_job(run_med_news_sync, trigger='cron', hour=2, minute=0)
        
        scheduler.add_job(run_email_ingest, trigger='interval', minutes=15)
        scheduler.add_job(run_calendar_sync, trigger='interval', minutes=30)
        scheduler.add_job(run_apple_reminders_sync, trigger='interval', minutes=30)
        
        scheduler.start()
    except Exception as e:
        logger.error(f"Scheduler fail: {e}")

    # LOG COMPLETION
    logger.info("✅ SERVER READY. Open http://localhost:5173 in your browser to begin.")

    yield # --- SERVER RUNNING ---

    # 2. SHUTDOWN
    if scheduler.running: scheduler.shutdown(wait=False)
    
    # Kill ingest process if active
    if ingest_process and ingest_process.is_alive():
        logger.info("Terminating ingest worker...")
        ingest_process.terminate()
        ingest_process.join()
        
    logger.info("Steward Backend Shutting Down.")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()

# --- INGEST PROCESS MANAGEMENT ---

async def trigger_ingest_logic():
    """Shared logic to spawn the ingest worker."""
    global ingest_process, ingest_status_queue
    
    # Check if running
    if ingest_process and ingest_process.is_alive():
        return False
    
    # Init Queue
    ingest_status_queue = Queue()
    
    # Get Settings to pass (cannot pass Async DB objects)
    settings = await get_all_settings()
    
    # Spawn Process
    ingest_process = Process(
        target=run_ingest_process, 
        args=(ingest_status_queue, settings)
    )
    ingest_process.start()
    return True

async def scheduled_ingest_check():
    """Background check: only runs if files are pending and process not running."""
    ingest_path = DOCS_PATH / STEWARD_INGEST_FOLDER
    has_files = any(f.is_file() for f in ingest_path.iterdir() if not f.name.startswith('.'))
    
    if has_files:
        logger.info("Scheduled Ingest: Found files, starting worker.")
        await trigger_ingest_logic()

@app.post("/api/ingest")
async def api_trigger_ingest():
    started = await trigger_ingest_logic()
    if not started:
        return {"status": "busy", "message": "Ingestion already running"}
    return {"status": "started"}

@app.get("/api/ingest/status")
async def get_ingest_status():
    global ingest_status_queue
    messages = []
    
    if ingest_status_queue:
        while not ingest_status_queue.empty():
            try:
                # Non-blocking fetch of all pending messages
                messages.append(ingest_status_queue.get_nowait())
            except: break
            
    running = ingest_process and ingest_process.is_alive()
    return {"running": running, "messages": messages}

# --- OTHER BACKGROUND JOBS ---

async def run_backup_job():
    logger.info("Running Nightly Backup...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_PATH / f"steward_backup_{timestamp}.zip"
    try:
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            if DB_STEWARD_PATH.exists(): zf.write(DB_STEWARD_PATH, DB_STEWARD_PATH.name)
    except Exception as e: logger.error(f"Backup failed: {e}")

@app.get("/api/health")
async def api_health_check():
    db_ok = False
    try:
        async with get_db_connection() as conn: pass
        db_ok = True
    except: pass
    return {"status": "ok", "db_status": db_ok, "mlx_status": "loading" if not await check_ollama_status() else "ready"}

# === MODEL ENDPOINTS (For Settings) ===
@app.get("/api/ollama/models")
async def api_get_models():
    """
    Mock Ollama endpoint to satisfy frontend settings page.
    Returns the locally configured MLX model and any others found in models/.
    """
    models = [{"name": DEFAULT_MLX_MODEL, "details": {"family": "mlx"}}]
    
    # Scan models directory for other downloaded models
    if MODELS_DIR.exists():
        for p in MODELS_DIR.iterdir():
            # Don't duplicate the default if it's already there
            if p.is_dir() and p.name != DEFAULT_MLX_MODEL:
                models.append({"name": p.name, "details": {"family": "local"}})
                
    return {"models": models}

# === ER CLINICAL AID ENDPOINTS ===
class ERPatientPayload(BaseModel):
    room: str
    complaint: str
    age_sex: str

class ERTextUpdatePayload(BaseModel):
    patient_id: int
    transcript: str

class MedSourcePayload(BaseModel):
    name: str
    url: str

@app.get("/api/er/dashboard")
async def api_er_dashboard(): return {"patients": await get_active_er_patients()}
@app.post("/api/er/patient")
async def api_create_er_patient(p: ERPatientPayload): pid = await create_er_patient(p.room, p.complaint, p.age_sex); return {"id": pid, "status": "success"}
@app.get("/api/er/chart/{pid}")
async def api_get_er_chart(pid: int): chart = await get_latest_er_chart(pid); return {"chart": chart}
@app.post("/api/er/update_text")
async def api_er_update_text(p: ERTextUpdatePayload): asyncio.create_task(process_er_audio_update(p.patient_id, p.transcript)); return {"status": "success", "message": "Agent processing..."}
@app.post("/api/er/archive/{pid}")
async def api_er_archive(pid: int, disposition: str = "Discharged"): await archive_er_patient(pid, disposition); return {"status": "success"}
@app.delete("/api/er/patient/{pid}")
async def api_er_delete(pid: int): await delete_er_patient(pid); return {"status": "success"}
@app.get("/api/er/sources")
async def api_get_sources(): return {"sources": await get_medical_sources()}
@app.post("/api/er/sources")
async def api_add_source(p: MedSourcePayload): await add_medical_source(p.name, p.url); return {"status": "success"}
@app.delete("/api/er/sources/{sid}")
async def api_delete_source(sid: int): await delete_medical_source(sid); return {"status": "success"}

@app.get("/api/er/status/{pid}")
async def api_er_status(pid: int):
    return {"status": ER_STATUS.get(pid, "")}

@app.post("/api/er/update_audio/{pid}")
async def api_er_update_audio(pid: int, file: UploadFile = File(...)):
    if not WHISPER_MODEL: 
        raise HTTPException(status_code=503, detail="Whisper unavailable.")
        
    temp_path = Path(tempfile.gettempdir()) / f"er_audio_{pid}_{datetime.now().timestamp()}.webm"
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE): await f.write(chunk)
            
        def _transcribe():
            # USES MEDICAL PROMPT FOR ACCURACY
            return WHISPER_MODEL.transcribe(str(temp_path), language="en", fp16=False, initial_prompt=MEDICAL_SPEECH_PROMPT)
            
        res = await asyncio.to_thread(_transcribe)
        transcript = res.get("text", "").strip()
        
        asyncio.create_task(process_er_audio_update(pid, transcript))
        return {"status": "success", "transcript": transcript, "message": "Agent processing..."}
    finally:
        if temp_path.exists(): os.remove(temp_path)

# === SETTINGS & MEMORY ===
class Settings(BaseModel): settings: dict
@app.get("/api/settings")
async def api_get_settings(): return {"settings": await get_all_settings()}
@app.post("/api/settings")
async def api_update_settings(p: Settings): await update_settings(p.settings); await load_rag_settings(); return {"status": "success"}

@app.get("/api/memory/facts")
async def api_get_facts(): return {"facts": await get_all_user_facts_structured()}
@app.delete("/api/memory/fact/{fact_id}")
async def api_delete_fact(fact_id: int): await delete_user_fact(fact_id); return {"status": "success"}

class PersonaPayload(BaseModel): name: str; icon: str; prompt: str
@app.get("/api/personas")
async def api_get_personas(): return {"personas": await get_personas()}
@app.post("/api/personas")
async def api_update_persona(p: PersonaPayload): await update_persona(p.name, p.icon, p.prompt); return {"status": "success"}
@app.delete("/api/personas/{name}")
async def api_delete_persona(name: str): await delete_persona(name); return {"status": "success"}

@app.post("/api/steward/run_job")
async def api_run_steward_job(): asyncio.create_task(run_daily_summary()); return {"status": "success", "message": "Steward job started."}
@app.post("/api/steward/run_finance_sync")
async def api_run_finance_sync(): asyncio.create_task(run_finance_sync()); return {"status": "success", "message": "Finance sync started."}
@app.post("/api/steward/run_med_news_sync")
async def api_run_med_news_sync(): asyncio.create_task(run_med_news_sync()); return {"status": "success", "message": "EM News sync started."}

class TaskPayload(BaseModel): task: str
class JournalPayload(BaseModel): content: str
@app.post("/api/steward/add_task")
async def api_add_steward_task(payload: TaskPayload):
    settings = await get_all_settings()
    folder = settings.get("steward_reminders_folder", STEWARD_REMINDERS_FOLDER)
    path = DOCS_PATH / folder / "reminders.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "a", encoding="utf-8") as f: await f.write(f"{payload.task.strip()}\n")
    try:
        success = await asyncio.to_thread(add_reminder_to_app, payload.task, "Inbox")
        msg = "Task added to File & Apple Reminders." if success else "Task added to File only."
    except: msg = "Task added to File only."
    await trigger_ingest_logic() # Trigger Ingest
    return {"status": "success", "message": msg}

@app.post("/api/steward/add_journal")
async def api_add_steward_journal(payload: JournalPayload):
    settings = await get_all_settings()
    folder = settings.get("steward_journal_folder", STEWARD_JOURNAL_FOLDER)
    path = DOCS_PATH / folder / datetime.now().strftime('%Y-%m-%d.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = f"\n\n### Entry @ {datetime.now().strftime('%H:%M:%S')}\n{payload.content.strip()}\n"
    async with aiofiles.open(path, "a", encoding="utf-8") as f: await f.write(entry)
    await trigger_ingest_logic() # Trigger Ingest
    return {"status": "success", "message": "Journal added."}

@app.post("/api/upload_and_transcribe/{folder}")
async def api_upload_and_transcribe(folder: str, file: UploadFile = File(...)):
    if not WHISPER_MODEL: raise HTTPException(status_code=503, detail="Whisper unavailable.")
    
    ingest_folder = (await get_all_settings()).get("steward_ingest_folder", STEWARD_INGEST_FOLDER)
    path = DOCS_PATH / ingest_folder
    path.mkdir(parents=True, exist_ok=True)
    safe_name = file.filename.replace('/', '_').replace('\\', '_')
    temp_path = path / f"temp_{safe_name}"
    
    async with aiofiles.open(temp_path, "wb") as f:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE): await f.write(chunk)
    
    txt_path = path / (os.path.splitext(safe_name)[0] + ".txt")
    try:
        def _transcribe():
            # USES MEDICAL PROMPT FOR ACCURACY
            return WHISPER_MODEL.transcribe(str(temp_path), verbose=False, language="en", fp16=False, initial_prompt=MEDICAL_SPEECH_PROMPT)
            
        res = await asyncio.to_thread(_transcribe)
        text = res.get("text", "").strip()
        header = f"# Voice Memo ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
        
        async with aiofiles.open(txt_path, "w", encoding="utf-8") as f: await f.write(header + text)
        await trigger_ingest_logic() # Trigger Ingest
    finally:
        if temp_path.exists(): os.remove(temp_path)
    return {"status": "success", "message": "Transcribed."}

class DailyHealthPayload(BaseModel):
    date: str
    steps: Optional[float] = 0.0
    active_calories: Optional[float] = 0.0
    weight: Optional[float] = 0.0
    resting_hr: Optional[float] = 0.0
    sleep_hours: Optional[float] = 0.0

@app.post("/api/ingest/apple_health")
async def api_ingest_apple_health(payload: DailyHealthPayload):
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO health_metrics (
                date, source, steps_count, active_calories, 
                weight_kg, resting_hr, sleep_total_duration
            ) VALUES (?, 'apple_shortcut', ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                steps_count=excluded.steps_count,
                active_calories=excluded.active_calories,
                weight_kg=excluded.weight_kg,
                resting_hr=excluded.resting_hr,
                sleep_total_duration=excluded.sleep_total_duration
        """, (payload.date, payload.steps, payload.active_calories, payload.weight, payload.resting_hr, f"{payload.sleep_hours} hr"))
        await conn.commit()

    settings = await get_all_settings()
    path = DOCS_PATH / settings.get("steward_health_folder", STEWARD_HEALTH_FOLDER)
    path.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path / f"health_log_{payload.date}.md", "w", encoding="utf-8") as f:
        await f.write(f"# Health Log: {payload.date}\n- Steps: {payload.steps}\n- Calories: {payload.active_calories}\n- Weight: {payload.weight} lbs\n- Sleep: {payload.sleep_hours} hrs\n- Resting HR: {payload.resting_hr} bpm\n")
    
    await trigger_ingest_logic() # Trigger Ingest
    return {"status": "success", "message": "Health data saved."}

@app.get("/api/backup/export")
async def api_backup_export():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if DB_STEWARD_PATH.exists(): zf.write(DB_STEWARD_PATH, DB_STEWARD_PATH.name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip", headers={'Content-Disposition': 'attachment; filename="backup.zip"'})

@app.post("/api/backup/import")
async def api_backup_import(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read()); tmp_path = tmp.name
    try:
        with zipfile.ZipFile(tmp_path, 'r') as zf: zf.extractall(path=BASE_DIR)
        await init_db()
        return {"status": "success"}
    finally: os.remove(tmp_path)

class TaskUpdate(BaseModel): status: str
@app.get("/api/steward/dashboard")
async def api_get_dashboard():
    settings = await get_all_settings()
    return {
        "suggestions": await get_latest_suggestion(),
        "tasks": await get_pending_tasks(),
        "events": await get_weeks_events_structured(),
        "journals": await get_recent_journals_structured(),
        "finance": await get_finance_structured(settings)
    }

@app.get("/api/steward/dashboard/memories")
async def api_get_memories(): return {"memories": await get_journal_memories()}
@app.get("/api/steward/dashboard/health")
async def api_get_health(): return {"health_metrics": await get_recent_health_metrics_structured()}
@app.post("/api/steward/task/{tid}")
async def api_update_task(tid: int, payload: TaskUpdate): await update_task_status(tid, payload.status); return {"status": "success"}

@app.get("/api/folders")
async def list_folders():
    if not DOCS_PATH.exists(): DOCS_PATH.mkdir(parents=True)
    ign = {"chroma_db", "whoosh_index", "steward.db", "venv", "node_modules", ".git", ".trash", "models"}
    return {"folders": sorted([d.name for d in DOCS_PATH.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in ign])}

@app.get("/api/files/{folder}")
async def list_files(folder: str):
    col = sanitize_collection_name(folder)
    path = DOCS_PATH / folder
    db_files = set()
    try:
        async with get_db_connection() as conn:
            async for row in await conn.execute("SELECT file_name FROM documents WHERE collection_name=? AND status='active'", (col,)): db_files.add(row['file_name'])
    except: pass
    files = []
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file() and not f.name.startswith('.'): files.append({"name": f.name, "status": "synced" if f.name in db_files else "pending"})
    return {"files": [{"name": "all", "status": "synced"}] + sorted(files, key=lambda x: x['name'])}

@app.get("/api/chat/sessions")
async def api_chat_sessions(): return {"sessions": await get_sessions()}
@app.post("/api/chat/session")
async def api_new_chat(): return {"session": await create_session(f"Chat {datetime.now().strftime('%m/%d %H:%M')}")}
@app.get("/api/chat/history/{sid}")
async def api_chat_history(sid: int): return {"messages": await get_chat_history(sid)}
class RenamePayload(BaseModel): name: str
@app.put("/api/chat/session/{sid}")
async def api_rename_chat(sid: int, p: RenamePayload): await update_chat_session_name(sid, p.name); return {"status": "success"}
@app.delete("/api/chat/session/{sid}")
async def api_delete_chat(sid: int): await delete_session(sid); return {"status": "success"}

@app.post("/api/upload/{folder}")
async def api_upload(folder: str, file: UploadFile = File(...)):
    path = DOCS_PATH / folder / file.filename
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE): await f.write(chunk)
    await trigger_ingest_logic() # Trigger Ingest
    return {"status": "success"}

@app.get("/api/document/preview/{folder}/{filename}")
async def api_preview(folder: str, filename: str):
    return {"content": await get_document_content(sanitize_collection_name(folder), filename), "filename": filename, "folder": folder}

@app.post("/api/ingest")
async def trigger_ingest(): 
    # Kept for backward compatibility, now aliases to api_trigger_ingest
    return await api_trigger_ingest()

class ClipPayload(BaseModel): url: str
@app.post("/api/clip")
async def api_clip_webpage(payload: ClipPayload):
    try:
        settings = await get_all_settings()
        path = DOCS_PATH / settings.get("steward_web_folder", "Steward_Web")
        path.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', payload.url.split("://")[-1])[:100]
        async with aiofiles.open(path / f"clip_{safe}.md", "w", encoding="utf-8") as f:
            await f.write(f"# Clip from: {payload.url}\n\n> {payload.content}\n")
        await trigger_ingest_logic() # Trigger Ingest
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/steward/audio-briefing")
async def api_audio_briefing(background_tasks: BackgroundTasks):
    sug = await get_latest_suggestion()
    if not sug: raise HTTPException(404, "No daily summary found.")
    text = f"Good morning. Here is your summary. {sug['content_private']}".replace("#", "").replace("*", "")
    path = await generate_audio_briefing(text)
    if not path: raise HTTPException(500, "TTS Failed")
    background_tasks.add_task(os.remove, path)
    return FileResponse(path, media_type="audio/mpeg", filename="briefing.mp3")

class TTSPayload(BaseModel): text: str
@app.post("/api/tts")
async def api_generate_tts(p: TTSPayload, background_tasks: BackgroundTasks):
    path = await generate_audio_briefing(p.text)
    if not path: raise HTTPException(status_code=500, detail="TTS generation failed.")
    background_tasks.add_task(os.remove, path)
    return FileResponse(path, media_type="audio/mpeg", filename="speech.mp3")

class DraftPayload(BaseModel): to: str; subject: str; body: str
@app.post("/api/steward/email-draft")
async def api_email_draft(p: DraftPayload):
    success = await create_draft_task(p.to, p.subject, p.body)
    if success: return {"status": "success", "message": "Draft saved."}
    else: raise HTTPException(500, "Failed to save draft.")

@app.get("/api/analysis/correlation")
async def api_correlation(): return {"data": await get_mood_health_correlation(30)}

@app.get("/api/steward/dashboard/sentiment")
async def api_get_sentiment(): return {"sentiment": await get_sentiment_history(days=30)}

class VoiceCommand(BaseModel): text: str
@app.post("/api/steward/voice_command")
async def api_voice_command(cmd: VoiceCommand):
    settings = await get_all_settings()
    folder = settings.get("steward_reminders_folder", STEWARD_REMINDERS_FOLDER)
    path = DOCS_PATH / folder / "voice_inbox.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "a", encoding="utf-8") as f: await f.write(f"{cmd.text.strip()}\n")
    await trigger_ingest_logic() # Trigger Ingest
    return {"status": "success", "message": "Command received"}

@app.websocket("/ws/audio")
async def ws_audio(ws: WebSocket):
    await ws.accept()
    if not WHISPER_MODEL: await ws.close(code=1011, reason="Whisper unavailable"); return
    
    temp_audio_path = Path(tempfile.gettempdir()) / f"stream_{datetime.now().timestamp()}.webm"
    try:
        async with aiofiles.open(temp_audio_path, 'wb') as f:
            while True:
                data = await ws.receive_bytes()
                if not data: break
                await f.write(data)
                await f.flush()
                
                def _transcribe():
                    # USES MEDICAL PROMPT FOR ACCURACY
                    return WHISPER_MODEL.transcribe(str(temp_audio_path), language="en", fp16=False, initial_prompt=MEDICAL_SPEECH_PROMPT)
                
                result = await asyncio.to_thread(_transcribe)
                text = result.get("text", "").strip()
                if text: await ws.send_text(text)
    except WebSocketDisconnect: pass
    except Exception: pass
    finally:
        if temp_audio_path.exists(): os.remove(temp_audio_path)

@app.websocket("/ws")
async def ws_rag(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            sid = data.get("session_id")
            folder = sanitize_collection_name(data.get("folder")) 
            filename = data.get("file")
            query = data.get("query")
            persona = data.get("persona", "Vault")
            lower_q = query.lower()
            
            await add_chat_message(sid, "user", query, persona="User")

            # === 1. STEWARD AGENT (Full Tools) ===
            # UPDATED: Route all "Active" personas through the agent to enable tools/scoped RAG
            AGENT_PERSONAS = {"Steward", "Clinical", "CFO", "Coach", "Mentor", "Vault"}
            
            if persona in AGENT_PERSONAS:
                full_resp = ""
                collected_sources = []
                
                # Check for dict tokens (Sources) vs string tokens (Text)
                async for token in agent_stream(query, sid, persona, folder, filename): 
                    if isinstance(token, dict) and token.get("type") == "sources":
                         # Forward the structured source data to the frontend
                         await ws.send_json(token)
                         collected_sources = token.get("data", [])
                    else:
                         await ws.send_json({"type": "token", "data": token})
                         full_resp += token
                
                # Persistence: Append hidden JSON source block to the message
                if collected_sources:
                     try:
                         src_str = json.dumps(collected_sources)
                         full_resp += f"\n<sources>{src_str}</sources>"
                     except: pass

                await add_chat_message(sid, "assistant", full_resp, persona=persona)
                await ws.send_json({"type": "done"})
                continue

            # === 2. CHAT (Bare LLM) ===
            if persona == "Chat":
                full_resp = ""
                async for token in generate_bare_stream(query, [], persona_name="Chat"):
                    await ws.send_json({"type": "token", "data": token})
                    full_resp += token
                await add_chat_message(sid, "assistant", full_resp, persona="Chat")
                await ws.send_json({"type": "done"})
                continue
            
            # Fallback (Should typically be covered by AGENT_PERSONAS)
            full_resp = ""
            collected_sources = []
            async for token in agent_stream(query, sid, persona, folder, filename):
                if isinstance(token, dict) and token.get("type") == "sources":
                    await ws.send_json(token)
                    collected_sources = token.get("data", [])
                else:
                    await ws.send_json({"type": "token", "data": token})
                    full_resp += token
            
            if collected_sources:
                 try:
                     src_str = json.dumps(collected_sources)
                     full_resp += f"\n<sources>{src_str}</sources>"
                 except: pass

            await add_chat_message(sid, "assistant", full_resp, persona=persona)
            await ws.send_json({"type": "done"})

    except WebSocketDisconnect: pass
    except Exception as e: logger.error(f"WS Error: {e}", exc_info=True)

assets_path = FRONTEND_PATH / "assets"
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    if full_path.startswith("api"): raise HTTPException(status_code=404)
    file_path = FRONTEND_PATH / full_path
    if file_path.exists() and file_path.is_file(): return FileResponse(file_path)
    index = FRONTEND_PATH / "index.html"
    if not index.exists(): return HTMLResponse("<h1>Frontend not built</h1>", status_code=404)
    return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

class CodePayload(BaseModel): code: str
@app.post("/api/steward/code")
async def api_run_code(p: CodePayload):
    output = await run_python_code(p.code)
    return {"output": output}

@app.get("/api/immich/search")
async def api_search_immich(query: str):
    return {"results": await search_immich_photos(query)}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)