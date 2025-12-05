import logging
import asyncio
import aiosqlite
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.database import get_all_settings, get_db_connection
from backend.config import DOCS_PATH

# Try to import caldav and icalendar, handle missing dependency
try:
    import caldav
    from icalendar import Calendar
except ImportError:
    caldav = None
    Calendar = None

logger = logging.getLogger(__name__)

# --- FIX: Suppress noisy caldav/vobject logs ---
logging.getLogger("caldav").setLevel(logging.ERROR)
logging.getLogger("vobject").setLevel(logging.ERROR)
logging.getLogger("icalendar").setLevel(logging.ERROR)

async def run_calendar_sync():
    """
    Connects to a CalDAV server (iCloud, Google, Nextcloud),
    fetches events AND tasks, and updates the DB.
    Uses icalendar to parse data to avoid vobject dependency issues.
    """
    logger.info("--- Running CalDAV Sync ---")
    
    if not caldav or not Calendar:
        logger.warning("caldav or icalendar library not installed. Skipping sync. Run 'pip install caldav icalendar'")
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
            try:
                calendars = principal.calendars()
            except Exception as e:
                logger.error(f"Failed to list calendars: {e}")
                return [], []
            
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
                # FIX: Increased delay to 5s to prevent iCloud 500 Rate Limit Errors
                time.sleep(5) 
                
                # Retry logic for 500 errors
                for attempt in range(2):
                    try:
                        # Fetch Events
                        events = cal.date_search(start, end)
                        all_events.extend(events)
                        
                        # Fetch Tasks (Todos)
                        todos = cal.todos(include_completed=False)
                        all_tasks.extend(todos)
                        break # Success, exit retry loop
                    except Exception as e:
                        if attempt == 0: 
                            time.sleep(5) # Wait a bit more before retry
                            continue
                        logger.warning(f"Failed to fetch from calendar {cal.name}: {e}")
            
            return all_events, all_tasks

        events, tasks = await asyncio.to_thread(fetch_caldav_data)
        logger.info(f"Fetched {len(events)} events and {len(tasks)} tasks from CalDAV.")

        # 2. Update Database (Using icalendar parsing to bypass vobject errors)
        async with get_db_connection() as conn:
            
            # --- Events ---
            e_count = 0
            for event_obj in events:
                try:
                    # FIX: Parse raw ICS data directly instead of accessing .instance
                    if not hasattr(event_obj, 'data') or not event_obj.data: 
                        continue
                        
                    cal_data = Calendar.from_ical(event_obj.data)
                    
                    # Walk through components to find events
                    for component in cal_data.walk('VEVENT'):
                        uid = str(component.get('UID'))
                        summary = str(component.get('SUMMARY'))
                        
                        dtstart_prop = component.get('DTSTART')
                        if not dtstart_prop: continue
                        start_time = dtstart_prop.dt
                        
                        # Normalize date objects to datetime
                        if not isinstance(start_time, datetime):
                            start_time = datetime.combine(start_time, datetime.min.time())

                        # Handle End Time vs Duration
                        end_time = None
                        if component.get('DTEND'):
                            end_time = component.get('DTEND').dt
                        elif component.get('DURATION'):
                            end_time = start_time + component.get('DURATION').dt
                        else:
                            end_time = start_time + timedelta(hours=1)
                            
                        if not isinstance(end_time, datetime):
                            end_time = datetime.combine(end_time, datetime.min.time())

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
                except Exception: 
                    pass
            
            # --- Tasks ---
            t_count = 0
            for task_obj in tasks:
                try:
                    if not hasattr(task_obj, 'data') or not task_obj.data: 
                        continue
                    
                    cal_data = Calendar.from_ical(task_obj.data)
                    
                    for component in cal_data.walk('VTODO'):
                        uid = str(component.get('UID'))
                        summary = str(component.get('SUMMARY'))
                        
                        status = 'pending'
                        # Check completion status loosely
                        if component.get('STATUS') == 'COMPLETED' or component.get('COMPLETED'):
                            status = 'completed'
                        
                        due_date = None
                        if component.get('DUE'):
                            dt = component.get('DUE').dt
                            due_date = dt if isinstance(dt, datetime) else datetime.combine(dt, datetime.min.time())

                        # Insert as 'pending'
                        await conn.execute("""
                            INSERT INTO tasks (task_uid, description, status, source_file, due_date)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(task_uid) DO UPDATE SET
                                description=excluded.description,
                                due_date=excluded.due_date,
                                last_updated=CURRENT_TIMESTAMP
                        """, (uid, summary, status, "CalDAV_Sync", due_date))
                        t_count += 1
                except Exception: 
                    pass

            await conn.commit()
            logger.info(f"Synced {e_count} events and {t_count} tasks.")

    except Exception as e:
        logger.error(f"CalDAV Sync Failed: {e}", exc_info=True)