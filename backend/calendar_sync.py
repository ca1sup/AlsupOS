
import logging
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.database import get_all_settings, get_db_connection
from backend.config import DOCS_PATH

# Try to import caldav, handle missing dependency
try:
    import caldav
except ImportError:
    caldav = None

logger = logging.getLogger(__name__)

async def run_calendar_sync():
    """
    Connects to a CalDAV server (iCloud, Google, Nextcloud),
    fetches events AND tasks, and updates the DB.
    """
    logger.info("--- Running CalDAV Sync ---")
    
    if not caldav:
        logger.warning("caldav library not installed. Skipping sync. Run 'pip install caldav'")
        return

    try:
        settings = await get_all_settings()
        
        url = settings.get("caldav_url")
        username = settings.get("caldav_username")
        password = settings.get("caldav_password")
        # calendar_name is optional. If None, we search all calendars.
        calendar_name = settings.get("caldav_calendar_name")

        if not url or not username or not password:
            logger.warning("CalDAV settings not configured. Skipping.")
            return

        # 1. Connect (Synchronous blocking call, run in thread)
        def fetch_caldav_data():
            client = caldav.DAVClient(url=url, username=username, password=password)
            principal = client.principal()
            calendars = principal.calendars()
            
            all_events = []
            all_tasks = []

            # If user specified a calendar, filter for it. Otherwise check all.
            target_calendars = calendars
            if calendar_name:
                # Split the input string by commas (e.g., "Home, Work, Kids")
                target_names = [n.strip().lower() for n in calendar_name.split(',')]
                
                # Keep the calendar if its name matches ANY of the names in your list
                filtered = [
                    c for c in calendars 
                    if any(name in (c.name or "").lower() for name in target_names)
                ]
                
                if filtered:
                    target_calendars = filtered

            # Fetch range: Now to +30 days
            start = datetime.now()
            end = start + timedelta(days=30)
            
            for cal in target_calendars:
                try:
                    # Fetch Events
                    events = cal.date_search(start, end)
                    all_events.extend(events)
                    
                    # Fetch Tasks (Todos)
                    # Note: date_search often doesn't work for todos in some CalDAV implementations
                    # so we fetch pending todos specifically
                    todos = cal.todos(include_completed=False)
                    all_tasks.extend(todos)
                except Exception as e:
                    logger.warning(f"Failed to fetch from calendar {cal.name}: {e}")
            
            return all_events, all_tasks

        events, tasks = await asyncio.to_thread(fetch_caldav_data)
        logger.info(f"Fetched {len(events)} events and {len(tasks)} tasks from CalDAV.")

        # 2. Update Database
        async with get_db_connection() as conn:
            
            # --- Events ---
            e_count = 0
            for event in events:
                try:
                    vevent = event.instance.vevent
                    uid = str(vevent.uid.value)
                    summary = str(vevent.summary.value)
                    dtstart = vevent.dtstart.value
                    start_time = dtstart if isinstance(dtstart, datetime) else datetime.combine(dtstart, datetime.min.time())

                    if hasattr(vevent, 'dtend'):
                        dtend = vevent.dtend.value
                        end_time = dtend if isinstance(dtend, datetime) else datetime.combine(dtend, datetime.min.time())
                    elif hasattr(vevent, 'duration'):
                        end_time = start_time + vevent.duration.value
                    else:
                        end_time = start_time + timedelta(hours=1)

                    await conn.execute("""
                        INSERT INTO events (event_uid, start_time, end_time, title, source_file)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(event_uid) DO UPDATE SET
                            start_time=excluded.start_time,
                            end_time=excluded.end_time,
                            title=excluded.title,
                            last_updated=CURRENT_TIMESTAMP
                    """, (uid, start_time, end_time, summary, "CalDAV_Sync"))
                    e_count += 1
                except Exception: pass
            
            # --- Tasks ---
            t_count = 0
            for task in tasks:
                try:
                    vtodo = task.instance.vtodo
                    uid = str(vtodo.uid.value)
                    summary = str(vtodo.summary.value)
                    
                    due_date = None
                    if hasattr(vtodo, 'due'):
                        dt = vtodo.due.value
                        due_date = dt if isinstance(dt, datetime) else datetime.combine(dt, datetime.min.time())

                    # Insert as 'pending'
                    await conn.execute("""
                        INSERT INTO tasks (task_uid, description, status, source_file, due_date)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(task_uid) DO UPDATE SET
                            description=excluded.description,
                            due_date=excluded.due_date,
                            last_updated=CURRENT_TIMESTAMP
                    """, (uid, summary, 'pending', "CalDAV_Sync", due_date))
                    t_count += 1
                except Exception: pass

            await conn.commit()
            logger.info(f"Synced {e_count} events and {t_count} tasks.")

    except Exception as e:
        logger.error(f"CalDAV Sync Failed: {e}", exc_info=True)
