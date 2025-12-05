import logging
import asyncio
import platform
import subprocess
from datetime import datetime
from dateutil.parser import parse as date_parse
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

def _escape_applescript_string(text):
    """Escapes characters that break AppleScript strings."""
    if not text: return ""
    # Escape backslashes first, then double quotes
    return text.replace('\\', '\\\\').replace('"', '\\"')

def _run_applescript(script, timeout=10):
    """
    Executes AppleScript and returns result.
    Includes a timeout to prevent hanging the server on large datasets.
    """
    if platform.system() != 'Darwin':
        return None
    try:
        # Use osascript with simple arguments and TIMEOUT
        result = subprocess.run(
            ['osascript', '-e', script], 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        if result.returncode != 0:
            # Log the error and the first 200 chars of script for context
            logger.error(f"AppleScript Error: {result.stderr.strip()} | Script start: {script[:200]}...")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"AppleScript timed out after {timeout}s.")
        return None
    except Exception as e:
        logger.error(f"AppleScript Exception: {e}")
        return None

def add_reminder_to_app(title, list_name="Inbox"):
    # Sanitize inputs to prevent syntax errors (-2741)
    safe_title = _escape_applescript_string(title)
    safe_list = _escape_applescript_string(list_name)
    
    script = f'''
    tell application "Reminders"
        if not (exists list "{safe_list}") then
            make new list with properties {{name:"{safe_list}"}}
        end if
        set myList to list "{safe_list}"
        make new reminder at end of myList with properties {{name:"{safe_title}"}}
    end tell
    '''
    return _run_applescript(script) is not None

def get_recently_completed_reminders():
    """
    Returns a list of reminder titles completed in the last 24 hours.
    Optimized to filter using 'whose' clause to avoid iterating all history.
    """
    script = '''
    tell application "Reminders"
        set oneDayAgo to ((current date) - 1 * days)
        try
            -- Optimization: Ask Reminders to filter for us
            set recentReminders to (every reminder whose completed is true and completion date > oneDayAgo)
            
            set output to ""
            repeat with aReminder in recentReminders
                set output to output & (name of aReminder) & linefeed
            end repeat
            return output
        on error
            return ""
        end try
    end tell
    '''
    # We allow a slightly longer timeout for fetching lists
    res = _run_applescript(script, timeout=30)
    return res.splitlines() if res else []

async def run_apple_reminders_sync():
    """
    Syncs PENDING Apple Reminders to the Steward DB 'tasks' table.
    Runs every 30 minutes via scheduler.
    """
    if platform.system() != 'Darwin': return

    logger.info("Running Apple Reminders (Local) Sync...")
    
    # Updated: Removed 'ISO 8601 string' usage which causes syntax errors in some envs.
    # We now simply coerce to string and let Python parse the format.
    script = '''
    tell application "Reminders"
        set output to ""
        -- Only fetch incomplete items to speed this up
        set todoList to (every reminder whose completed is false)
        
        repeat with anItem in todoList
            set d to due date of anItem
            set dStr to ""
            if d is not missing value then
                try
                    set dStr to (d as string)
                on error
                    set dStr to ""
                end try
            end if
            
            set itemId to id of anItem as string
            set itemName to name of anItem as string
            
            set output to output & itemId & "||" & itemName & "||" & dStr & linefeed
        end repeat
        return output
    end tell
    '''
    
    # INCREASED TIMEOUT to 120s to fix "AppleScript timed out" error
    raw_output = await asyncio.to_thread(_run_applescript, script, 120)
    if not raw_output: return

    async with get_db_connection() as conn:
        count = 0
        for line in raw_output.splitlines():
            if not line.strip(): continue
            try:
                parts = line.split("||")
                if len(parts) < 2: continue
                
                uid = parts[0]
                title = parts[1]
                due_date_str = parts[2] if len(parts) > 2 and parts[2] else None
                
                # Parse date if present using robust dateutil
                parsed_date = None
                if due_date_str:
                    try: 
                        parsed_date = date_parse(due_date_str)
                    except: pass

                await conn.execute("""
                    INSERT INTO tasks (task_uid, description, status, source_file, due_date)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(task_uid) DO UPDATE SET
                        description=excluded.description,
                        due_date=excluded.due_date,
                        last_updated=CURRENT_TIMESTAMP
                """, (uid, title, 'pending', 'Apple_Reminders_Local', parsed_date))
                count += 1
            except Exception as e:
                logger.error(f"Failed to sync reminder line: {e}")
        
        await conn.commit()
        logger.info(f"Synced {count} local Apple Reminders.")