import logging
import json
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

async def ensure_er_schema():
    """
    Ensures the ER table and columns exist.
    Run this lazily before operations to avoid startup race conditions.
    """
    async with get_db_connection() as db:
        # 1. Create Table if it doesn't exist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS er_patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT,
                complaint TEXT,
                age_sex TEXT,
                chart_content TEXT,
                advisor_analysis TEXT,
                dictation_history TEXT,
                recommendation_history TEXT,
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """.replace('\\"', '"')) 
        
        # 2. Add columns if missing (Safe Migration)
        async with db.execute("PRAGMA table_info(er_patients)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            
            # Chart & Analysis columns
            if 'chart_content' not in columns:
                try: await db.execute("ALTER TABLE er_patients ADD COLUMN chart_content TEXT"); logger.info("Migrated DB: Added chart_content")
                except Exception as e: logger.warning(f"Migration warning: {e}")
            if 'advisor_analysis' not in columns:
                try: await db.execute("ALTER TABLE er_patients ADD COLUMN advisor_analysis TEXT"); logger.info("Migrated DB: Added advisor_analysis")
                except Exception as e: logger.warning(f"Migration warning: {e}")

            # History columns (New)
            if 'dictation_history' not in columns:
                try: await db.execute("ALTER TABLE er_patients ADD COLUMN dictation_history TEXT"); logger.info("Migrated DB: Added dictation_history")
                except Exception as e: logger.warning(f"Migration warning: {e}")
            if 'recommendation_history' not in columns:
                try: await db.execute("ALTER TABLE er_patients ADD COLUMN recommendation_history TEXT"); logger.info("Migrated DB: Added recommendation_history")
                except Exception as e: logger.warning(f"Migration warning: {e}")
        
        await db.commit()

async def get_active_er_patients():
    """Fetches all patients with status 'Active'."""
    await ensure_er_schema()
    async with get_db_connection() as db:
        db.row_factory = None
        async with db.execute("SELECT * FROM er_patients WHERE status = 'Active' ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            cols = [description[0] for description in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

async def get_er_patient_data(patient_id: int):
    """Fetches a single patient's full data."""
    await ensure_er_schema()
    async with get_db_connection() as db:
        db.row_factory = None 
        async with db.execute("SELECT * FROM er_patients WHERE id = ?", (patient_id,)) as cursor:
            row = await cursor.fetchone()
            if not row: return None
            
            cols = [description[0] for description in cursor.description]
            data = dict(zip(cols, row))
            
            # Parse JSON fields safely
            try: data['dictation_history'] = json.loads(data['dictation_history']) if data.get('dictation_history') else []
            except: data['dictation_history'] = []
            
            try: data['recommendation_history'] = json.loads(data['recommendation_history']) if data.get('recommendation_history') else []
            except: data['recommendation_history'] = []
            
            return data

async def save_er_chart(patient_id: int, chart_content: str, advisor_analysis: str, dictation_history: list = None, recommendation_history: list = None):
    """Updates the patient record with new chart and analysis data."""
    await ensure_er_schema()
    
    updates = ["chart_content = ?", "advisor_analysis = ?"]
    params = [chart_content, advisor_analysis]
    
    if dictation_history is not None:
        updates.append("dictation_history = ?")
        params.append(json.dumps(dictation_history))
        
    if recommendation_history is not None:
        updates.append("recommendation_history = ?")
        params.append(json.dumps(recommendation_history))
        
    params.append(patient_id)
    
    sql = f"UPDATE er_patients SET {', '.join(updates)} WHERE id = ?"
    
    async with get_db_connection() as db:
        await db.execute(sql, tuple(params))
        await db.commit()