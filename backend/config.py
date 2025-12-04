# backend/config.py
import os
import re
from pathlib import Path

# === BASE PATHS ===
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_PATH = BASE_DIR / "docs"
DATA_PATH = BASE_DIR / "data"
LOGS_PATH = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"
FRONTEND_PATH = BASE_DIR / "dist"
BACKUP_PATH = BASE_DIR / "backups"

# === DATABASE & INDICES ===
DB_STEWARD_PATH = DATA_PATH / "steward.db"
DB_PATH = DB_STEWARD_PATH 
CHROMA_PATH = BASE_DIR / "chroma_db"
WHOOSH_PATH = BASE_DIR / "whoosh_index"
MANIFEST_PATH = FRONTEND_PATH / "manifest.json"

# === FOLDER MAPPINGS ===
STEWARD_INGEST_FOLDER = "Inbox"
STEWARD_MEDICAL_FOLDER = "Emergency Medicine" 
STEWARD_FINANCE_FOLDER = "Finance"
STEWARD_HEALTH_FOLDER = "Health"
STEWARD_WORKOUT_FOLDER = "Workouts"
STEWARD_MEALPLANS_FOLDER = "Meal Plans"
STEWARD_JOURNAL_FOLDER = "Journal"
STEWARD_CONTEXT_FOLDER = "Context"
STEWARD_REMINDERS_FOLDER = "Reminders"

# --- ADDITIONAL MODULE FOLDERS ---
STEWARD_CALENDAR_FOLDER = "Calendar"
STEWARD_WEB_FOLDER = "Web_Clips"
STEWARD_NUTRITION_FOLDER = "Nutrition"
STEWARD_HOMESCHOOL_FOLDER = "Homeschool"
STEWARD_WORSHIP_FOLDER = "Family Worship"
STEWARD_CURRICULUM_FOLDER = "Curriculum"

# === MODEL SETTINGS ===
DEFAULT_MLX_MODEL = "lmstudio-community/Qwen3-30B-A3B-Instruct-2507-MLX-6bit"

# UPDATED: High-Fidelity Reranker (Matches Qwen Embedding quality)
DEFAULT_RERANKER_MODEL = "mixedbread-ai/mxbai-rerank-large-v1"

# UPDATED: Qwen3 Embedding (0.6B Params, 32k Context)
EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"

# --- VOICE MODELS ---
# STT: Optimized for Mac/MLX (High Accuracy)
STT_MODEL_NAME = "mlx-community/whisper-large-v3-turbo"

# TTS: Local Kokoro Model (82M params, High Fidelity)
TTS_MODEL_NAME = "mlx-community/Kokoro-82M-bf16"

# Valid Voices for Kokoro-82M:
# American (a): af_heart, af_bella, af_nicole, af_sarah, af_sky, am_adam, am_michael
# British (b): bf_emma, bf_isabella, bm_lewis
TTS_VOICE = "am_adam" 

# === CLINICAL SETTINGS ===
# Primes Whisper to recognize medical terms correctly
MEDICAL_SPEECH_PROMPT = (
    "Medical Dictation. History of Present Illness. "
    "Hypertension, Hyperlipidemia, Diabetes Mellitus, COPD, CHF, Atrial Fibrillation. "
    "Lisinopril, Metoprolol, Atorvastatin, Metformin, Albuterol, Eliquis. "
    "CBC, BMP, Troponin, EKG, Chest X-Ray, CT Head, Ultrasound. "
    "Patient is a 45-year-old male presenting with chest pain and shortness of breath."
)

# === SYSTEM SETTINGS ===
UPLOAD_CHUNK_SIZE = 1024 * 1024 * 50  
WS_RECEIVE_TIMEOUT = 300.0       
WS_HEARTBEAT_INTERVAL = 30.0     

# UPDATED: Increased Search Depth for M1 Ultra
DEFAULT_SEARCH_K = 20            # Fetch 20 docs instead of 5
RERANK_TOP_N = 100               # Re-sort top 100 candidates
HYBRID_SEARCH_K_MULTIPLIER = 2.0 
EMBEDDING_BATCH_SIZE = 50

# === SUPPORTED FILE TYPES ===
SUPPORTED_EXTENSIONS = [
    ".txt", ".ics", ".md", ".json", ".csv",
    ".mp3", ".wav", ".m4a", ".ogg", ".flac",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".pdf"
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}

# === UTILITIES ===
def sanitize_collection_name(name: str) -> str:
    if not name: return "default"
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())
    clean = re.sub(r'_{2,}', '_', clean)
    clean = clean.strip('_')
    if len(clean) < 3: clean += "_col"
    return clean[:63]

for p in [DOCS_PATH, DATA_PATH, LOGS_PATH, MODELS_DIR, BACKUP_PATH]:
    p.mkdir(parents=True, exist_ok=True)