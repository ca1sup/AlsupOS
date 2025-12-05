# backend/email_ingest.py
import asyncio
import logging
import imaplib
import email
import json
import re
import aiofiles
from email.header import decode_header
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# --- HACK: Add base_dir to sys.path ---
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))
# --- End HACK ---

from backend.database import get_all_settings, init_db, get_db_connection
from backend.config import DB_STEWARD_PATH, DOCS_PATH, STEWARD_WORSHIP_FOLDER

logger = logging.getLogger(__name__)

# List of known columns in the health_metrics table
KNOWN_HEALTH_COLUMNS = {
    "date", "source", "weight_kg", "active_calories", "steps_count",
    "distance_walking_running_km", "hrv_ms", "resting_hr", "vo2_max",
    "sleep_total_duration", "sleep_in_bed_duration",
    "walking_asymmetry_percent", "walking_step_length_cm"
}

def _parse_json_health_data(payload: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(payload)
        if not data.get("date"): return None
        health_data = {"date": data["date"], "source": "apple_health_json"}
        for key, value in data.items():
            if key in KNOWN_HEALTH_COLUMNS and key != "date" and value is not None and value != "":
                health_data[key] = value
        return health_data
    except: return None

def _parse_text_sleep_data(payload: str) -> Optional[Dict[str, Any]]:
    try:
        data = {}
        date_match = re.search(r"^([a-zA-Z]{3} \d{1,2}, \d{4})", payload)
        if not date_match: return None
        data["date"] = datetime.strptime(date_match.group(1), "%b %d, %Y").strftime("%Y-%m-%d")
        data["source"] = "apple_health_sleep_text"
        
        total = re.search(r"Total Time Asleep:([\w\s]+)", payload)
        if total: data["sleep_total_duration"] = total.group(1).strip()
        
        bed = re.search(r"In Bed for ([\w\s]+)", payload)
        if bed: data["sleep_in_bed_duration"] = bed.group(1).strip()
        
        return data if "sleep_total_duration" in data or "sleep_in_bed_duration" in data else None
    except: return None

def _parse_worship_email(payload: str) -> Optional[str]:
    """
    Parses 'First Things' or Liturgy details from Pastor Tim's email.
    """
    try:
        # Simple extraction logic: Look for "First Things" or common liturgy markers
        # This can be refined based on the exact email format
        if "First Things" in payload or "Order of Worship" in payload:
            return payload
        return None
    except: return None

async def _save_worship_log(content: str):
    try:
        path = DOCS_PATH / STEWARD_WORSHIP_FOLDER
        path.mkdir(parents=True, exist_ok=True)
        filename = f"worship_guide_{datetime.now().strftime('%Y-%m-%d')}.txt"
        async with aiofiles.open(path / filename, "w", encoding="utf-8") as f:
            await f.write(content)
        logger.info(f"Saved worship guide: {filename}")
    except Exception as e:
        logger.error(f"Failed to save worship log: {e}")

async def _write_health_data_to_db(parsed_data_with_ids: List[Tuple[Dict[str, Any], str]]) -> List[str]:
    """
    Writes data to DB and returns list of email IDs that were successful.
    """
    successful_ids = []
    if not parsed_data_with_ids: return []

    try:
        async with get_db_connection() as conn:
            for health_data, email_id in parsed_data_with_ids:
                try:
                    cols = []
                    vals = []
                    for key, value in health_data.items():
                        if key in KNOWN_HEALTH_COLUMNS and value is not None and value != "":
                            cols.append(key)
                            vals.append(value)
                    
                    if len(cols) <= 2: continue # Skip if no data

                    cols_str = ", ".join(cols)
                    placeholders = ", ".join(["?"] * len(vals))
                    sql = f"INSERT OR REPLACE INTO health_metrics ({cols_str}) VALUES ({placeholders})"
                    
                    await conn.execute(sql, vals)
                    await conn.commit()
                    successful_ids.append(email_id)
                    
                except Exception as e:
                    logger.error(f"Failed to write health data: {e}")
                    await conn.rollback()

        return successful_ids

    except Exception as e:
        logger.error(f"Fatal DB error: {e}")
        return []

async def run_email_ingest():
    logger.info("--- Running Email Ingest Job ---")
    try:
        await init_db()
        settings = await get_all_settings()
        server = settings.get("imap_server")
        email_addr = settings.get("imap_email")
        password = settings.get("imap_password")
        
        if not server or not email_addr or not password or password == "YOUR_APP_PASSWORD":
            return

        # Fetch and Parse (Sync Thread)
        # Returns: Tuple of (health_data_list, worship_content_list)
        health_payloads, worship_payloads, processed_ids = await asyncio.to_thread(
            _process_emails_thread, server, email_addr, password, 
            settings.get("imap_subject_filter"), settings.get("imap_subject_filter_sleep")
        )
        
        # 1. Write Health to DB
        success_health_ids = await _write_health_data_to_db(health_payloads)
        
        # 2. Save Worship to File
        success_worship_ids = []
        for content, eid in worship_payloads:
            await _save_worship_log(content)
            success_worship_ids.append(eid)

        # 3. Mark all as Seen
        all_success = success_health_ids + success_worship_ids
        if all_success:
            await asyncio.to_thread(_mark_emails_as_seen, server, email_addr, password, all_success)
            
    except Exception as e:
        logger.error(f"Email Ingest Failed: {e}")

def _process_emails_thread(server, email_addr, password, h_subj, s_subj) -> Tuple[List, List, List]:
    health_results = []
    worship_results = []
    processed_ids = []
    
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(email_addr, password)
        mail.select("inbox")
        
        # Combined Search: Health OR Sleep OR Worship Sender
        # Note: IMAP search syntax is picky. We do separate searches to be safe.
        
        # 1. Health Search
        search_query = f'(OR (SUBJECT "{h_subj}") (SUBJECT "{s_subj}"))'
        status, messages = mail.search(None, 'UNSEEN', search_query)
        
        if status == "OK":
            for eid_bytes in messages[0].split():
                eid = eid_bytes.decode('utf-8')
                try:
                    payload = _fetch_payload(mail, eid_bytes)
                    if payload:
                        data = None
                        if h_subj in payload or "Date" in payload: data = _parse_json_health_data(payload)
                        if not data and (s_subj in payload or "Sleep" in payload): data = _parse_text_sleep_data(payload)
                        
                        if data: health_results.append((data, eid))
                except: pass

        # 2. Worship Search (Sender Based)
        # Assuming sender is 'timothy@cfcutah.org' - adjust as needed
        status, messages = mail.search(None, 'UNSEEN', '(FROM "timothy@cfcutah.org")')
        if status == "OK":
             for eid_bytes in messages[0].split():
                eid = eid_bytes.decode('utf-8')
                try:
                    payload = _fetch_payload(mail, eid_bytes)
                    if payload:
                        worship_data = _parse_worship_email(payload)
                        if worship_data: worship_results.append((worship_data, eid))
                except: pass

        mail.logout()
        return health_results, worship_results, processed_ids
    except Exception: return [], [], []

def _fetch_payload(mail, eid_bytes):
    _, msg_data = mail.fetch(eid_bytes, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])
    
    payload = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break
    else:
        payload = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    return payload

def _mark_emails_as_seen(server, email_addr, password, ids: List[str]):
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(email_addr, password)
        mail.select("inbox")
        for i in ids:
            try: mail.store(i.encode('utf-8'), '+FLAGS', '\\Seen')
            except: pass
        mail.logout()
    except: pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_email_ingest())