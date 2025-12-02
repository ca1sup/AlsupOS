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
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Add columns if missing (Safe Migration)
        async with db.execute("PRAGMA table_info(er_patients)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            
            if 'chart_content' not in columns:
                try:
                    await db.execute("ALTER TABLE er_patients ADD COLUMN chart_content TEXT")
                    logger.info("Migrated DB: Added chart_content to er_patients")
                except Exception as e: logger.warning(f"Migration warning: {e}")
                
            if 'advisor_analysis' not in columns:
                try:
                    await db.execute("ALTER TABLE er_patients ADD COLUMN advisor_analysis TEXT")
                    logger.info("Migrated DB: Added advisor_analysis to er_patients")
                except Exception as e: logger.warning(f"Migration warning: {e}")
        
        await db.commit()

async def get_er_patient_data(patient_id: int):
    await ensure_er_schema()
    async with get_db_connection() as db:
        db.row_factory = None # Reset to default or handle Row objects
        async with db.execute("SELECT * FROM er_patients WHERE id = ?", (patient_id,)) as cursor:
            # Fetch row and convert to dict
            row = await cursor.fetchone()
            if not row: return None
            
            # Get column names to create a proper dict
            cols = [description[0] for description in cursor.description]
            return dict(zip(cols, row))

async def save_er_chart(patient_id: int, chart_content: str, advisor_analysis: str):
    await ensure_er_schema()
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE er_patients 
            SET chart_content = ?, advisor_analysis = ?
            WHERE id = ?
        """, (chart_content, advisor_analysis, patient_id))
        await db.commit()