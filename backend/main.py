# backend/main.py
# Force Tokenizers to run sequentially to prevent Metal/Fork crashes on macOS
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# CRITICAL FIX: Enforce 'spawn' start method for multiprocessing on macOS
# This prevents child processes from inheriting corrupted Metal/GPU contexts.
import multiprocessing
try:
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass

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
import gc
from contextlib import asynccontextmanager
from multiprocessing import Process, Queue
from urllib.parse import unquote # Added for safe model deletion

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

# NEW: Import ER DB functions directly to ensure read/write consistency
from backend.er_db import get_active_er_patients, get_er_patient_data

# Ingest Worker Import
from backend.ingest import run_ingest_process

# Centralized Voice Logic (TTS & STT)
try:
    from backend.tts import generate_audio_briefing, get_whisper_model, load_whisper_model
except ImportError:
    # Fallbacks if backend.tts fails completely
    async def generate_audio_briefing(text): return ""
    async def get_whisper_model(): return None
    async def load_whisper_model(): return None

from backend.email_tools import create_draft_task
from backend.analysis import get_mood_health_correlation, analyze_sentiment_simple
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
    STEWARD_WORKOUT_FOLDER,
    STEWARD_NUTRITION_FOLDER,
    STEWARD_MEDICAL_FOLDER,
    BACKUP_PATH, LOGS_PATH,
    MEDICAL_SPEECH_PROMPT,
    MODELS_DIR,          
    DEFAULT_MLX_MODEL    
)
from backend.rag import (
    search_file, generate_stream, generate_bare_stream,
    get_document_content,
    get_whoosh_index, perform_rag_query,
    init_llm, reload_llm, 
    check_ollama_status
)
from backend.rag import load_settings as load_rag_settings
from backend.prompts import ATTENDING_CONSULT_PROMPT

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
    create_er_patient, 
    # Removed legacy ER imports to avoid confusion
    archive_er_patient, delete_er_patient,
    get_medical_sources, add_medical_source, delete_medical_source,
    init_db, get_sessions, create_session, delete_session,
    get_chat_history, get_folders, get_files_in_folder,
    get_er_dashboard_data, 
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

# --- GLOBAL INGEST STATE & LOCKS ---
ingest_process: Optional[Process] = None
ingest_status_queue: Optional[Queue] = None

# MLX Lock: Serializes access to GPU/Metal resources
MLX_LOCK = asyncio.Lock()

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP
    logger.info("⚡ Steward Backend Starting...")
    await init_db()
    
    # Load settings into memory before init_llm so we know which model to pick
    await load_rag_settings()
    
    # Init MLX LLM (Chat Model)
    asyncio.create_task(init_llm())

    # Pre-load MLX Whisper Model
    asyncio.create_task(load_whisper_model())

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

# === MODEL MANAGER ENDPOINTS ===

def get_folder_size(path: Path) -> str:
    """Returns directory size in readable format."""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if total < 1024.0:
                return f"{total:.2f} {unit}"
            total /= 1024.0
    except: pass
    return "Unknown"

@app.get("/api/models")
async def api_get_models():
    """Returns list of downloaded models in MODELS_DIR."""
    models = []
    
    # 1. Scan Local Models Directory
    if MODELS_DIR.exists():
        candidates = [p for p in MODELS_DIR.iterdir() if p.is_dir() and not p.name.startswith('.')]
        for p in candidates:
            if (p / "config.json").exists():
                models.append({
                    "name": p.name,
                    "size": get_folder_size(p),
                    "path": str(p),
                    "source": "Local (MLX)"
                })
            else:
                for sub in p.iterdir():
                    if sub.is_dir() and (sub / "config.json").exists():
                        rel_name = f"{p.name}/{sub.name}"
                        models.append({
                            "name": rel_name,
                            "size": get_folder_size(sub),
                            "path": str(sub),
                            "source": "Local (MLX)"
                        })

    # 2. Add Default if missing (Virtual entry)
    if not any(m['name'] == DEFAULT_MLX_MODEL for m in models):
        models.append({
            "name": DEFAULT_MLX_MODEL,
            "size": "Not Downloaded",
            "path": "",
            "source": "Remote (Hugging Face)"
        })
        
    return {"models": models}

class PullModelPayload(BaseModel):
    repo_id: str

def _download_model_task(repo_id: str):
    """Background task to download model using huggingface_hub."""
    try:
        logger.info(f"📥 Starting download for {repo_id}...")
        from huggingface_hub import snapshot_download
        
        target_dir = MODELS_DIR / repo_id
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False
        )
        logger.info(f"✅ Download complete: {repo_id}")
    except Exception as e:
        logger.error(f"❌ Failed to download {repo_id}: {e}")

@app.post("/api/models/pull")
async def api_pull_model(payload: PullModelPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(_download_model_task, payload.repo_id)
    return {"status": "started", "message": f"Downloading {payload.repo_id} in background..."}

@app.delete("/api/models/{model_id:path}")
async def api_delete_model(model_id: str):
    try:
        decoded_id = unquote(model_id)
        target_path = (MODELS_DIR / decoded_id).resolve()
        
        if not str(target_path).startswith(str(MODELS_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
            
        if target_path.exists() and target_path.is_dir():
            shutil.rmtree(target_path)
            parent = target_path.parent
            if parent != MODELS_DIR and not any(parent.iterdir()):
                try: parent.rmdir()
                except: pass
            return {"status": "success", "message": f"Deleted {decoded_id}"}
        else:
            raise HTTPException(status_code=404, detail="Model not found")
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === FILE SYSTEM ENDPOINTS ===
@app.get("/api/folders")
async def api_get_folders():
    return {"folders": await get_folders()}

@app.get("/api/files/{folder}")
async def api_get_files(folder: str):
    files = await get_files_in_folder(folder)
    return {"files": files}

# === CHAT SESSION ENDPOINTS ===
@app.get("/api/chat/sessions")
async def api_get_sessions():
    return {"sessions": await get_sessions()}

@app.post("/api/chat/session")
async def api_create_session():
    session = await create_session("New Session")
    return {"session": session}

@app.delete("/api/chat/session/{session_id}")
async def api_delete_session(session_id: int):
    await delete_session(session_id)
    return {"status": "success"}

class RenameSessionPayload(BaseModel): name: str
@app.put("/api/chat/session/{session_id}")
async def api_rename_session(session_id: int, payload: RenameSessionPayload):
    await update_chat_session_name(session_id, payload.name)
    return {"status": "success"}

@app.get("/api/chat/history/{session_id}")
async def api_get_chat_history(session_id: int):
    history = await get_chat_history(session_id, lightweight=False)
    return {"messages": history}

# === DASHBOARD ENDPOINTS ===
@app.get("/api/steward/dashboard")
async def api_steward_dashboard_data():
    return {
        "suggestions": await get_latest_suggestion(),
        "tasks": await get_pending_tasks(),
        "events": await get_weeks_events_structured(),
        "finance": { "summary": "Finance sync pending", "budget_used": "0%" } 
    }

@app.get("/api/steward/dashboard/health")
async def api_steward_dashboard_health():
    return {"health_metrics": await get_recent_health_metrics_structured(7)}

class TaskStatusPayload(BaseModel): status: str
@app.post("/api/steward/task/{tid}")
async def api_update_task(tid: int, payload: TaskStatusPayload):
    await update_task_status(tid, payload.status)
    return {"status": "success"}

# === ER CLINICAL AID ENDPOINTS ===

# Wrapper to safely run the ER Agent within the MLX Lock
# This prevents the background agent from clashing with foreground transcription/chat
async def safe_er_agent_task(pid: int, transcript: str):
    # CRITICAL: Wait 2.0s (was 0.5s) to let Metal/GPU flush pending commands from the Whisper job
    await asyncio.sleep(2.0)
    
    async with MLX_LOCK:
        logger.info(f"🔒 MLX Lock Acquired for Agent (Patient {pid})")
        try:
            await process_er_audio_update(pid, transcript)
        except Exception as e:
            logger.error(f"❌ Error in ER Agent: {e}", exc_info=True)
        finally:
            logger.info(f"🔓 MLX Lock Released (Patient {pid})")

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
async def api_er_dashboard(): 
    # Use the new DB accessor directly
    return {"patients": await get_active_er_patients()}

@app.post("/api/er/patient")
async def api_create_er_patient(p: ERPatientPayload): 
    pid = await create_er_patient(p.room, p.complaint, p.age_sex); 
    return {"id": pid, "status": "success"}

@app.get("/api/er/chart/{pid}")
async def api_get_er_chart(pid: int): 
    # FIX: Read from the new DB source (er_db) instead of legacy database.py
    data = await get_er_patient_data(pid)
    if not data:
        return {"chart": None}
    
    # MAP: Transform keys to match what Frontend expects
    # DB: chart_content, advisor_analysis
    # FE Expects: chart_markdown, clinical_guidance_json
    chart = {
        "id": data.get("id"),
        "patient_id": data.get("id"),
        "chart_markdown": data.get("chart_content", ""),
        "clinical_guidance_json": data.get("advisor_analysis", ""),
        "created_at": data.get("created_at")
    }
    return {"chart": chart}

@app.post("/api/er/update_text")
async def api_er_update_text(p: ERTextUpdatePayload): 
    # Use safe wrapper to respect MLX Lock
    asyncio.create_task(safe_er_agent_task(p.patient_id, p.transcript))
    return {"status": "success", "message": "Agent processing..."}

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
    model = await get_whisper_model()
    if not model: 
        raise HTTPException(status_code=503, detail="Whisper unavailable (Loading or Missing).")
    
    # --- FIX: Preserve File Extension for FFmpeg (Mac/Safari Support) ---
    original_ext = Path(file.filename).suffix.lower()
    if not original_ext: original_ext = ".webm" # Fallback
    
    temp_path = Path(tempfile.gettempdir()) / f"er_audio_{pid}_{datetime.now().timestamp()}{original_ext}"
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE): await f.write(chunk)
            
        def _transcribe():
            return model.transcribe(str(temp_path), initial_prompt=MEDICAL_SPEECH_PROMPT)
            
        # Protect Transcription with Lock and Logging
        async with MLX_LOCK:
            logger.info("🔒 MLX Lock Acquired for Whisper")
            res = await asyncio.to_thread(_transcribe)
            logger.info("🔓 MLX Lock Released after Whisper")
            
        transcript = res.get("text", "").strip()
        
        # EXPLICIT CLEANUP: Remove reference and force GC to clear Metal buffers
        del res
        gc.collect()
        
        # Schedule Agent Task (which also acquires lock internally)
        asyncio.create_task(safe_er_agent_task(pid, transcript))
        
        return {"status": "success", "transcript": transcript, "message": "Agent processing..."}
    finally:
        if temp_path.exists(): os.remove(temp_path)

# === SETTINGS & MEMORY ===
class Settings(BaseModel): settings: dict
@app.get("/api/settings")
async def api_get_settings(): return {"settings": await get_all_settings()}

@app.post("/api/settings")
async def api_update_settings(p: Settings):
    # Detect Model Switch
    current = await get_all_settings()
    old_model = current.get("llm_model")
    
    await update_settings(p.settings)
    await load_rag_settings()
    
    new_model = p.settings.get("llm_model")
    
    # If the model changed, trigger a background reload so we don't block the UI response
    if new_model and new_model != old_model:
        logger.info(f"🔄 Model switch detected: {old_model} -> {new_model}. Triggering reload.")
        asyncio.create_task(reload_llm())
        
    return {"status": "success"}

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

# === VOICE & JOURNALING ===

class NotePayload(BaseModel):
    category: str
    content: str

@app.post("/api/steward/transcribe_temp")
async def api_transcribe_temp(file: UploadFile = File(...)):
    model = await get_whisper_model()
    if not model: 
        raise HTTPException(status_code=503, detail="Whisper unavailable (Loading or Missing).")
    
    # --- FIX: Preserve File Extension here too ---
    original_ext = Path(file.filename).suffix.lower()
    if not original_ext: original_ext = ".webm"

    temp_path = Path(tempfile.gettempdir()) / f"temp_transcribe_{datetime.now().timestamp()}{original_ext}"
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE): await f.write(chunk)
            
        def _transcribe():
            return model.transcribe(str(temp_path))
            
        async with MLX_LOCK:
            res = await asyncio.to_thread(_transcribe)
            
        transcript = res.get("text", "").strip()
        return {"transcript": transcript}
    finally:
        if temp_path.exists(): os.remove(temp_path)

@app.post("/api/steward/save_note")
async def api_save_note(p: NotePayload):
    settings = await get_all_settings()
    
    folder_key_map = {
        "Nutrition": "steward_nutrition_folder",
        "Workout": "steward_workout_folder",
        "Journal": "steward_journal_folder",
        "Reminder": "steward_reminders_folder",
        "Inbox": "steward_ingest_folder"
    }
    
    default_folders = {
        "Nutrition": STEWARD_NUTRITION_FOLDER,
        "Workout": STEWARD_WORKOUT_FOLDER,
        "Journal": STEWARD_JOURNAL_FOLDER,
        "Reminder": STEWARD_REMINDERS_FOLDER,
        "Inbox": STEWARD_INGEST_FOLDER
    }
    
    folder_key = folder_key_map.get(p.category, "steward_journal_folder")
    folder_name = settings.get(folder_key, default_folders.get(p.category, STEWARD_JOURNAL_FOLDER))
    
    path = DOCS_PATH / folder_name
    path.mkdir(parents=True, exist_ok=True)
    
    filename = f"{datetime.now().strftime('%Y-%m-%d')}.md"
    if p.category == "Reminder": filename = "reminders.txt"
    if p.category == "Inbox": filename = f"note_{datetime.now().strftime('%H%M%S')}.md"
    
    # === NEW: Journal Sentiment Integration ===
    if p.category == "Journal":
        # Run sentiment analysis on the raw content
        score, mag = analyze_sentiment_simple(p.content)
        # Store in DB
        async with get_db_connection() as db:
            await db.execute(
                "INSERT INTO sentiment_log (date, score, magnitude, source_text) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), score, mag, p.content[:200]) # Store snippet
            )
            await db.commit()
    # ==========================================

    file_path = path / filename
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
        if p.category == "Reminder":
            await f.write(f"\\n[ ] {p.content.strip()}")
            try: await asyncio.to_thread(add_reminder_to_app, p.content.strip(), "Inbox")
            except: pass
        else:
            await f.write(f"\\n\\n### {p.category} Entry @ {timestamp}\\n{p.content.strip()}\\n")
            
    await trigger_ingest_logic()
    return {"status": "success"}

class TaskPayload(BaseModel): task: str
class JournalPayload(BaseModel): content: str
@app.post("/api/steward/add_task")
async def api_add_steward_task(payload: TaskPayload):
    return await api_save_note(NotePayload(category="Reminder", content=payload.task))

@app.post("/api/steward/add_journal")
async def api_add_steward_journal(payload: JournalPayload):
    return await api_save_note(NotePayload(category="Journal", content=payload.content))

@app.post("/api/upload/{folder}")
async def api_upload(folder: str, files: list[UploadFile] = File(...)):
    ingest_folder = folder if folder != "all" else (await get_all_settings()).get("steward_ingest_folder", STEWARD_INGEST_FOLDER)
    path = DOCS_PATH / ingest_folder
    path.mkdir(parents=True, exist_ok=True)
    
    for file in files:
        file_path = path / file.filename
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE): 
                await f.write(chunk)
                
    await trigger_ingest_logic() 
    return {"status": "success"}

@app.get("/api/document/preview/{folder}/{filename}")
async def api_preview(folder: str, filename: str):
    return {"content": await get_document_content(sanitize_collection_name(folder), filename), "filename": filename, "folder": folder}

@app.post("/api/ingest")
async def trigger_ingest(): 
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
            await f.write(f"# Clip from: {payload.url}\\n\\n> {payload.content}\\n")
        await trigger_ingest_logic()
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
    return FileResponse(path, media_type="audio/wav", filename="briefing.wav")

class TTSPayload(BaseModel): text: str
@app.post("/api/tts")
async def api_generate_tts(p: TTSPayload, background_tasks: BackgroundTasks):
    path = await generate_audio_briefing(p.text)
    if not path: raise HTTPException(status_code=500, detail="TTS generation failed.")
    background_tasks.add_task(os.remove, path)
    return FileResponse(path, media_type="audio/wav", filename="speech.wav")

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
    async with aiofiles.open(path, "a", encoding="utf-8") as f: await f.write(f"{cmd.text.strip()}\\n")
    await trigger_ingest_logic()
    return {"status": "success", "message": "Command received"}

@app.websocket("/ws/audio")
async def ws_audio(ws: WebSocket):
    await ws.accept()
    model = await get_whisper_model()
    if not model: await ws.close(code=1011, reason="Whisper unavailable"); return
    
    temp_audio_path = Path(tempfile.gettempdir()) / f"stream_{datetime.now().timestamp()}.webm"
    try:
        async with aiofiles.open(temp_audio_path, 'wb') as f:
            while True:
                data = await ws.receive_bytes()
                if not data: break
                await f.write(data)
                await f.flush()
                def _transcribe():
                    return model.transcribe(str(temp_audio_path), initial_prompt=MEDICAL_SPEECH_PROMPT)
                
                # Protect Streaming Transcription
                async with MLX_LOCK:
                    result = await asyncio.to_thread(_transcribe)
                    
                text = result.get("text", "").strip()
                if text: await ws.send_text(text)
    except WebSocketDisconnect: pass
    except Exception: pass
    finally:
        if temp_audio_path.exists(): os.remove(temp_audio_path)

@app.websocket("/ws/clinical_consult/{patient_id}")
async def ws_clinical_consult(ws: WebSocket, patient_id: int):
    """
    Dedicated WebSocket for discussing a specific patient with RAG support.
    """
    await ws.accept()
    try:
        while True:
            # 1. Receive User Query
            user_msg = await ws.receive_text()
            
            # 2. Fetch Patient Context (Live)
            patient = await get_er_patient_data(patient_id)
            if not patient:
                await ws.send_text("Error: Patient not found.")
                continue

            # Construct Transcript from history list
            transcript_history = patient.get("dictation_history", [])
            transcript_str = "\n".join([f"- {t}" for t in transcript_history]) if transcript_history else "No transcript available."
            
            # Construct Chart
            chart_str = patient.get("chart_content", "No chart content.")

            # 3. Construct Context Prompt
            full_context = f"""
            === PATIENT CONTEXT ===
            ID: {patient_id}
            Room: {patient.get('room', 'Unknown')}
            Age/Sex: {patient.get('age_sex', 'Unknown')}
            Complaint: {patient.get('complaint', 'Unknown')}

            === CHART ===
            {chart_str}

            === TRANSCRIPT HISTORY ===
            {transcript_str}
            """

            # 4. Stream Response with "Attending" persona and RAG enabled
            # We explicitly force the "Emergency Medicine" folder for RAG search scope
            async with MLX_LOCK:
                full_resp = ""
                collected_sources = []
                
                # Stream generator
                async for token in agent_stream(
                    query=user_msg,
                    session_id=0, # Ephemeral session
                    persona="Clinical", # Use Clinical logic/persona
                    folder=STEWARD_MEDICAL_FOLDER, # Force EM RAG scope
                    file=None,
                    history=[{"role": "system", "content": ATTENDING_CONSULT_PROMPT + "\n" + full_context}]
                ):
                    if isinstance(token, dict) and token.get("type") == "sources":
                        # Send sources to UI immediately
                        await ws.send_json(token)
                        collected_sources = token.get("data", [])
                    else:
                        # Send text token
                        await ws.send_json({"type": "token", "data": token})
                        full_resp += token
                
                # Append sources XML if any were found (consistency with main chat)
                if collected_sources:
                    try:
                        src_str = json.dumps(collected_sources)
                        # We don't need to append to text stream for UI, 
                        # but if we were saving history, we would.
                    except: pass

                await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Consult WS Error: {e}", exc_info=True)

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
            
            await add_chat_message(sid, "user", query, persona="User")
            history_objs = await get_chat_history(sid, lightweight=True)
            chat_history = [{"role": h['role'], "content": h['content']} for h in history_objs[-10:]]

            # EXPANDED Persona List for the "Steward Protocol"
            AGENT_PERSONAS = {"Steward", "Clinical", "CFO", "Coach", "Mentor", "Vault", "Chef", "Citizen"}
            
            # Wrap RAG Generation in Lock to prevent collision with Whisper or other Agents
            async with MLX_LOCK:
                if persona in AGENT_PERSONAS:
                    full_resp = ""
                    collected_sources = []
                    async for token in agent_stream(query, sid, persona, folder, filename, history=chat_history): 
                        if isinstance(token, dict) and token.get("type") == "sources":
                            await ws.send_json(token)
                            collected_sources = token.get("data", [])
                        else:
                            await ws.send_json({"type": "token", "data": token})
                            full_resp += token
                    
                    if collected_sources:
                        try:
                            src_str = json.dumps(collected_sources)
                            full_resp += f"\\n<sources>{src_str}</sources>"
                        except: pass

                    await add_chat_message(sid, "assistant", full_resp, persona=persona)
                    await ws.send_json({"type": "done"})
                    continue

                if persona == "Chat":
                    full_resp = ""
                    async for token in generate_bare_stream(query, chat_history, persona_name="Chat"):
                        await ws.send_json({"type": "token", "data": token})
                        full_resp += token
                    await add_chat_message(sid, "assistant", full_resp, persona="Chat")
                    await ws.send_json({"type": "done"})
                    continue
                
                # Fallback
                full_resp = ""
                collected_sources = []
                async for token in agent_stream(query, sid, persona, folder, filename, history=chat_history):
                    if isinstance(token, dict) and token.get("type") == "sources":
                        await ws.send_json(token)
                        collected_sources = token.get("data", [])
                    else:
                        await ws.send_json({"type": "token", "data": token})
                        full_resp += token
                
                if collected_sources:
                    try:
                        src_str = json.dumps(collected_sources)
                        full_resp += f"\\n<sources>{src_str}</sources>"
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