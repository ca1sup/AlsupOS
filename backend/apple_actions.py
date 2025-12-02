import logging
import asyncio
import platform
import subprocess
from datetime import datetime
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

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
            logger.error(f"AppleScript Error: {result.stderr}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("AppleScript timed out (took too long to fetch reminders).")
        return None
    except Exception as e:
        logger.error(f"AppleScript Exception: {e}")
        return None

def add_reminder_to_app(title, list_name="Inbox"):
    script = f'''
    tell application "Reminders"
        if not (exists list "{list_name}") then
            make new list with properties {{name:"{list_name}"}}
        end if
        set myList to list "{list_name}"
        make new reminder at end of myList with properties {{name:"{title}"}}
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
                set output to output & (name of aReminder) & "\n"
            end repeat
            return output
        on error
            return ""
        end try
    end tell
    '''
    # We allow a slightly longer timeout for fetching lists
    res = _run_applescript(script, timeout=15)
    return res.splitlines() if res else []

async def run_apple_reminders_sync():
    """
    Syncs PENDING Apple Reminders to the Steward DB 'tasks' table.
    Runs every 30 minutes via scheduler.
    """
    if platform.system() != 'Darwin': return

    logger.info("Running Apple Reminders (Local) Sync...")
    
    # Updated to use a 'whose' filter for speed, reducing the items we loop over
    script = '''
    tell application "Reminders"
        set output to ""
        -- Only fetch incomplete items to speed this up
        set todoList to (every reminder whose completed is false)
        
        repeat with anItem in todoList
            set d to due date of anItem
            set dStr to ""
            if d is not missing value then
                set dStr to (ISO 8601 string of d)
            end if
            
            set itemId to id of anItem as string
            set itemName to name of anItem as string
            
            set output to output & itemId & "||" & itemName & "||" & dStr & "\n"
        end repeat
        return output
    end tell
    '''
    
    raw_output = await asyncio.to_thread(_run_applescript, script, 30)
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
                due_date = parts[2] if len(parts) > 2 and parts[2] else None
                
                # Parse date if present
                parsed_date = None
                if due_date:
                    try: parsed_date = datetime.fromisoformat(due_date)
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