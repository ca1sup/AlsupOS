import aiosqlite
import json
import logging
import asyncio
from datetime import datetime, timedelta
from backend.config import DB_PATH, DOCS_PATH, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

# --- INIT ---
async def init_db():
    # Ensure directory exists before connecting
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        # === HIGH PERFORMANCE CONFIGURATION (M1/M2 Optimized) ===
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA mmap_size=2147483648;") 
        await db.execute("PRAGMA cache_size=-1000000;")
        await db.execute("PRAGMA temp_store=MEMORY;")
        
        # 1. Settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # 2. Chat Sessions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 3. Messages
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                role TEXT,
                content TEXT,
                sources TEXT,
                persona TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            )
        """)
        # 4. Facts
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 5. Tasks 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_uid TEXT UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'pending',
                due_date TIMESTAMP,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 6. Events
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_uid TEXT UNIQUE,
                title TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                location TEXT,
                source_file TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 7. Health
        await db.execute("""
            CREATE TABLE IF NOT EXISTS health_metrics (
                date TEXT PRIMARY KEY,
                source TEXT,
                steps_count INTEGER,
                active_calories REAL,
                weight_kg REAL,
                resting_hr INTEGER,
                sleep_total_duration TEXT,
                sleep_in_bed_duration TEXT,
                hrv_ms INTEGER,
                vo2_max REAL,
                walking_asymmetry_percent REAL,
                walking_step_length_cm REAL,
                distance_walking_running_km REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 8. Suggestions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_public TEXT,
                content_private TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 9. Personas
        await db.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                name TEXT PRIMARY KEY,
                icon TEXT,
                prompt TEXT
            )
        """)
        # 10. Cache
        await db.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                query_hash TEXT PRIMARY KEY,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 11. Sentiment 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                score REAL,
                magnitude REAL,
                source_text TEXT
            )
        """)

        # 12. File Tags
        await db.execute("""
            CREATE TABLE IF NOT EXISTS file_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                tag TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(filename, tag)
            )
        """)

        # 13. ER Patients 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS er_patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_label TEXT,
                chief_complaint TEXT,
                age_sex TEXT,
                status TEXT DEFAULT 'Active',
                acuity_level INTEGER DEFAULT 3,
                disposition TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 14. ER Chart History 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS er_chart_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                chart_markdown TEXT,
                ai_scratchpad TEXT,
                clinical_pearls TEXT,
                differentials TEXT,
                audio_transcript_chunk TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clinical_guidance_json TEXT,
                guidance_version INTEGER DEFAULT 0,
                FOREIGN KEY(patient_id) REFERENCES er_patients(id) ON DELETE CASCADE
            )
        """)

        # 15. Medical Sources 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS medical_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url_pattern TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        # 16. Documents (RAG Tracking)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_name TEXT,
                file_name TEXT,
                file_hash TEXT,
                file_mtime REAL DEFAULT 0, -- NEW: For Smart Diffing
                last_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                UNIQUE(collection_name, file_name)
            )
        """)

        # 17. Chunks (RAG Content)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER,
                vector_db_id TEXT,
                chunk_hash TEXT,
                metadata_json TEXT,
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            )
        """)

        # === MIGRATIONS (Safe updates for existing DBs) ===
        try:
            await db.execute("ALTER TABLE er_chart_history ADD COLUMN clinical_guidance_json TEXT")
        except Exception: pass
        
        try:
            await db.execute("ALTER TABLE er_chart_history ADD COLUMN guidance_version INTEGER DEFAULT 0")
        except Exception: pass

        # NEW: Migration for Smart Diffing
        try:
            await db.execute("ALTER TABLE documents ADD COLUMN file_mtime REAL DEFAULT 0")
        except Exception: pass

        await init_personas(db)
        await seed_default_prompts(db)
        await db.commit()

async def seed_default_prompts(db):
    """Seeds the editable prompts into settings if they don't exist."""
    
    defaults = {
        # 1. CLINICAL
        "er_system_scribe": """You are an expert Emergency Medicine Scribe.
Your goal is to maintain a specific, high-quality Markdown chart.
You will receive the CURRENT CHART and a NEW TRANSCRIPT.
You must merge the new information into the chart.
Do NOT delete existing history unless explicitly corrected.
CRITICAL INSTRUCTION:
You must strictly adhere to the MASTER CHART TEMPLATE provided.
If a section has no data yet, leave it as 'Not documented'.
Do not hallucinate. Be concise.""",

        "er_system_attending": """You are a senior Emergency Medicine attending physician providing clinical decision support.
YOUR ROLE: Analyze the complete clinical picture and provide evidence-based guidance.
CRITICAL MANDATE:
- Be PROACTIVE: Don't wait to be asked
- Be SPECIFIC: Give exact doses, timing, test names
- Be EVIDENCE-BASED: Cite guidelines when available
- Be SAFETY-FOCUSED: Flag dangerous patterns immediately
- Think about "Can't Miss" diagnoses first""",

        "er_master_chart_template": """MDM:
Differentials (ranked): <List>
Encounter summary: <2-4 sentences>
Test interpretations: <Concise>
Clinical decision tools: <Score -> Impact>
Rule outs: <Diagnosis -> Basis>
Final impression: <Dx + Certainty>
Disposition: <Plan>

HPI:
Chief complaint: <>
Onset/Timing: <>
Location/Radiation: <>
Quality/Severity: <>
Assoc. Symptoms: <>
Modifying Factors: <>
History/Meds/Allergies: <>

Physical Exam:
General: <>
Vitals: <>
HEENT: <>
CV: <>
Lungs: <>
Abd: <>
Neuro/Ext: <>

Results:
<Test> - <Result> - <Interp>""",

        "med_news_refresher_prompt": """Generate one single, high-yield clinical pearl for an Emergency Medicine physician. Be concise. Example: 'For PEA, remember the H's and T's...'"""
    }

    for key, val in defaults.items():
        # INSERT OR IGNORE ensures we don't overwrite user edits on restart
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

async def init_personas(db):
    """Seeds the Core Triad Personas if they don't exist."""
    triad = [
        ("Vault", "BookOpen", "You are The Vault. You are a strict librarian..."),
        ("Steward", "Activity", "You are The Steward. You are the executive assistant..."),
        ("Sage", "Sparkles", "You are The Sage. You are a creative mentor...")
    ]
    for name, icon, prompt in triad:
        await db.execute("INSERT OR IGNORE INTO personas (name, icon, prompt) VALUES (?, ?, ?)", (name, icon, prompt))

def get_db_connection():
    return aiosqlite.connect(DB_PATH, timeout=60.0)

# --- SETTINGS ---
async def get_all_settings():
    async with get_db_connection() as db:
        async with db.execute("SELECT key, value FROM settings") as cursor:
            return {row[0]: row[1] for row in await cursor.fetchall()}

async def update_settings(new_settings: dict):
    async with get_db_connection() as db:
        for k, v in new_settings.items():
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
        await db.commit()

# --- CHAT SESSIONS ---
async def get_sessions():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chat_sessions ORDER BY created_at DESC") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def create_session(name: str):
    async with get_db_connection() as db:
        cursor = await db.execute("INSERT INTO chat_sessions (name) VALUES (?)", (name,))
        await db.commit()
        return {"id": cursor.lastrowid, "name": name, "created_at": datetime.now().isoformat()}

async def update_session_name(sid: int, name: str):
    async with get_db_connection() as db:
        await db.execute("UPDATE chat_sessions SET name = ? WHERE id = ?", (name, sid))
        await db.commit()

async def delete_session(sid: int):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
        await db.commit()

async def prune_old_chat_sessions(days=30):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    async with get_db_connection() as db:
        await db.execute("DELETE FROM chat_sessions WHERE created_at < ?", (cutoff,))
        await db.commit()

# --- MESSAGES ---
async def get_chat_history(session_id: int, lightweight=False):
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        cols = "role, content" if lightweight else "*"
        async with db.execute(f"SELECT {cols} FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def add_chat_message(session_id, role, content, sources=None, persona="Vault"):
    async with get_db_connection() as db:
        if role == 'user':
            from backend.analysis import analyze_sentiment_simple
            score, mag = analyze_sentiment_simple(content)
            try:
                await db.execute("INSERT INTO sentiment_log (date, score, magnitude, source_text) VALUES (?, ?, ?, ?)", 
                                (datetime.now().isoformat(), score, mag, content[:50]))
            except Exception:
                pass 

        await db.execute(
            "INSERT INTO messages (session_id, role, content, sources, persona) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, json.dumps(sources) if sources else None, persona)
        )
        await db.commit()

# --- SUGGESTIONS / DASHBOARD ---
async def get_latest_suggestion():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM suggestions ORDER BY created_at DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def save_suggestion(public, private):
    async with get_db_connection() as db:
        await db.execute("INSERT INTO suggestions (content_public, content_private) VALUES (?, ?)", (public, private))
        await db.commit()

# --- TASKS ---
async def get_pending_tasks():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE status != 'completed' ORDER BY created_at DESC") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def update_task_status(tid, status):
    async with get_db_connection() as db:
        await db.execute("UPDATE tasks SET status = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?", (status, tid))
        await db.commit()

# --- FILE SYSTEM ROUTES (Dynamic) ---
async def get_folders():
    """
    Returns a list of folders in the DOCS_PATH.
    Always includes 'all' as the first option.
    """
    folders = ["all"]
    if DOCS_PATH.exists():
        for item in DOCS_PATH.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                folders.append(item.name)
    return folders

async def get_files_in_folder(folder: str):
    """
    Returns a list of files in the specified folder.
    """
    files = []
    
    if folder == 'all':
        # Flatten all folders
        if DOCS_PATH.exists():
            for item in DOCS_PATH.rglob('*'):
                if item.is_file() and not item.name.startswith('.') and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append({"name": item.name, "status": "synced"})
    else:
        # Specific folder (case-insensitive check)
        target_dir = DOCS_PATH / folder
        if not target_dir.exists():
            # Try finding it regardless of case
            for item in DOCS_PATH.iterdir():
                if item.is_dir() and item.name.lower() == folder.lower():
                    target_dir = item
                    break
        
        if target_dir.exists() and target_dir.is_dir():
            for item in target_dir.iterdir():
                if item.is_file() and not item.name.startswith('.') and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append({"name": item.name, "status": "synced"})
                    
    return files
    
# --- EVENTS ---
async def get_todays_events():
    start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
    end = datetime.now().replace(hour=23, minute=59, second=59).isoformat()
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE start_time BETWEEN ? AND ? ORDER BY start_time", (start, end)) as cursor:
            rows = await cursor.fetchall()
            return "\n".join([f"- {row['title']} at {row['start_time']}" for row in rows]) if rows else "No events today."

async def get_weeks_events_structured():
    start = datetime.now().isoformat()
    end = (datetime.now() + timedelta(days=7)).isoformat()
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE start_time BETWEEN ? AND ? ORDER BY start_time", (start, end)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

# --- JOURNAL / MEMORY ---
async def get_recent_journals_content(days=3):
    return "Recent journal entries not indexed in DB yet." 

async def get_recent_journals_structured():
    return []

async def get_journal_memories():
    return []

# --- HEALTH ---
async def get_recent_health_metrics_structured(days=7):
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM health_metrics ORDER BY date DESC LIMIT ?", (days,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def get_most_recent_workout_date_and_exercises():
    return None

# --- FACTS ---
async def add_user_fact(fact: str):
    async with get_db_connection() as db:
        await db.execute("INSERT INTO user_facts (fact) VALUES (?)", (fact,))
        await db.commit()

async def get_all_user_facts():
    async with get_db_connection() as db:
        async with db.execute("SELECT fact FROM user_facts ORDER BY created_at DESC") as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def get_all_user_facts_structured():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_facts ORDER BY created_at DESC") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def delete_user_fact(fid):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM user_facts WHERE id = ?", (fid,))
        await db.commit()

# --- PERSONAS ---
async def get_personas():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM personas") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def update_persona(name, icon, prompt):
    async with get_db_connection() as db:
        await db.execute("INSERT OR REPLACE INTO personas (name, icon, prompt) VALUES (?, ?, ?)", (name, icon, prompt))
        await db.commit()

async def delete_persona(name):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM personas WHERE name = ?", (name,))
        await db.commit()

# --- CACHE ---
async def get_cached_response(query_hash):
    async with get_db_connection() as db:
        async with db.execute("SELECT response FROM semantic_cache WHERE query_hash = ?", (query_hash,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def cache_response(query_hash, response):
    async with get_db_connection() as db:
        await db.execute("INSERT OR REPLACE INTO semantic_cache (query_hash, response) VALUES (?, ?)", (query_hash, response))
        await db.commit()

# --- MODULE HELPERS ---
async def get_last_worship_log(): return "No recent worship logs."
async def get_recent_homeschool_logs(): return "No recent homeschool logs."
async def get_sentiment_history(days=30):
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sentiment_log ORDER BY date DESC LIMIT ?", (days,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def add_file_tag(filename: str, tag: str):
    async with get_db_connection() as db:
        await db.execute("INSERT OR IGNORE INTO file_tags (filename, tag) VALUES (?, ?)", (filename, tag))
        await db.commit()

# --- ER MODULE ACCESSORS ---
async def create_er_patient(room: str, complaint: str, age_sex: str):
    async with get_db_connection() as db:
        cursor = await db.execute(
            "INSERT INTO er_patients (room_label, chief_complaint, age_sex) VALUES (?, ?, ?)", 
            (room, complaint, age_sex)
        )
        await db.commit()
        return cursor.lastrowid

async def get_active_er_patients():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM er_patients WHERE status = 'Active' ORDER BY created_at DESC") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def get_er_dashboard_data():
    return await get_active_er_patients()

async def get_er_patient(pid: int):
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM er_patients WHERE id = ?", (pid,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def archive_er_patient(pid: int, disposition: str):
    async with get_db_connection() as db:
        await db.execute("UPDATE er_patients SET status = 'Archived', disposition = ? WHERE id = ?", (disposition, pid))
        await db.commit()

async def delete_er_patient(pid: int):
    """Hard delete of a patient and their chart history."""
    async with get_db_connection() as db:
        await db.execute("DELETE FROM er_chart_history WHERE patient_id = ?", (pid,))
        await db.execute("DELETE FROM er_patients WHERE id = ?", (pid,))
        await db.commit()

async def get_latest_er_chart(pid: int):
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM er_chart_history WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 1", (pid,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_er_chart(pid: int):
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM er_chart_history WHERE patient_id = ? ORDER BY timestamp ASC", (pid,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def update_er_chart(pid: int, chart_md: str, scratchpad: str, transcript: str, pearls: str = None, diffs: str = None, clinical_guidance_json: str = None, guidance_version: int = 0):
    """
    Enhanced update function supporting new structured data.
    """
    async with get_db_connection() as db:
        await db.execute(
            """INSERT INTO er_chart_history 
               (patient_id, chart_markdown, ai_scratchpad, audio_transcript_chunk, clinical_pearls, differentials, clinical_guidance_json, guidance_version) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, chart_md, scratchpad, transcript, pearls, diffs, clinical_guidance_json, guidance_version)
        )
        await db.execute("UPDATE er_patients SET last_updated = CURRENT_TIMESTAMP WHERE id = ?", (pid,))
        await db.commit()

# --- MEDICAL SOURCES ACCESSORS ---
async def get_medical_sources():
    async with get_db_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM medical_sources WHERE is_active = 1") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def add_medical_source(name: str, url: str):
    async with get_db_connection() as db:
        await db.execute("INSERT INTO medical_sources (name, url_pattern) VALUES (?, ?)", (name, url))
        await db.commit()

async def delete_medical_source(sid: int):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM medical_sources WHERE id = ?", (sid,))
        await db.commit()