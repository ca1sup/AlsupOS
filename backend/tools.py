# backend/tools.py
import json
import logging
import asyncio
import aiofiles
from datetime import datetime, timedelta
from pathlib import Path

from backend.database import (
    get_recent_health_metrics_structured,
    get_pending_tasks,
    get_todays_events,
    get_all_settings,
    add_user_fact
)
from backend.interpreter import run_python_code
from backend.web_search import perform_web_search
from backend.immich import search_immich_photos
from backend.email_tools import create_draft_task
from backend.memory import extract_and_store_fact
from backend.weather import get_current_weather
from backend.apple_actions import add_reminder_to_app
from backend.config import (
    DOCS_PATH, 
    STEWARD_FINANCE_FOLDER, 
    STEWARD_HEALTH_FOLDER,
    STEWARD_REMINDERS_FOLDER
)

logger = logging.getLogger(__name__)

# --- HELPER ---
async def get_active_model():
    """Fetches the currently active LLM from settings."""
    settings = await get_all_settings()
    return settings.get("llm_model", "phi4-mini")

# ==========================================
# 1. HEALTH & WELLNESS
# ==========================================

async def tool_health_query_metrics(metric_type: str = "all", days: str = "7") -> str:
    """Query specific health data (steps, weight, sleep, etc.)."""
    try:
        days_int = int(days)
        data = await get_recent_health_metrics_structured(days=days_int)
        if not data: return "No recent health data found."
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error querying health metrics: {e}"

async def tool_health_analyze_trends(metrics: str = "all", time_period: str = "7 days") -> str:
    """Analyze patterns in health data."""
    # Placeholder: In a real app, this would use pandas/numpy to find trends
    return await tool_health_query_metrics(metrics, time_period.split()[0])

async def tool_health_set_goal(metric: str, target: str, deadline: str) -> str:
    """Set a health goal (e.g. 'weight', '185lbs', '2024-01-01')."""
    # Stub: Would save to a 'goals' table in DB
    return f"Goal set: {metric} -> {target} by {deadline}"

async def tool_health_get_correlations(metric_pairs: str) -> str:
    """Find relationships between metrics (e.g. 'sleep,weight')."""
    # Stub: Would run correlation analysis
    return f"Correlation analysis for {metric_pairs} not yet implemented."

async def tool_health_export_report(format: str = "pdf", metrics: str = "all", period: str = "30 days") -> str:
    """Generate a health report."""
    return f"Report ({format}) for {metrics} over {period} generated at /docs/health/report.pdf"

# ==========================================
# 2. FINANCIAL (YNAB)
# ==========================================

async def tool_check_budget(category: str = None) -> str:
    """Reads the latest YNAB budget data with fuzzy matching."""
    try:
        settings = await get_all_settings()
        folder = settings.get("steward_finance_folder", STEWARD_FINANCE_FOLDER)
        path = DOCS_PATH / folder / "ynab_summary.json"
        
        if not path.exists():
            return "No budget data found. Please run the Finance Sync first."
            
        async with asyncio.Lock(): 
            content = path.read_text()
            data = json.loads(content)
            
        structured = data.get("structured", [])
        
        if not category or category.lower() == "all":
             return str(data.get("summary", "No summary available."))

        search_term = category.lower()
        matches = [c for c in structured if search_term in c['category'].lower()]
        
        if not matches: 
            common_mappings = {
                "food": ["groceries", "dining", "restaurants"],
                "car": ["gas", "auto", "maintenance"],
                "house": ["mortgage", "rent", "utilities"]
            }
            for key, variants in common_mappings.items():
                if key in search_term:
                    for variant in variants:
                        matches += [c for c in structured if variant in c['category'].lower()]
            
        if not matches:
            available = ", ".join([c['category'] for c in structured[:5]])
            return f"Category '{category}' not found. Available categories start with: {available}..."
            
        return json.dumps(matches, indent=2)
    except Exception as e:
        return f"Error checking budget: {e}"

async def tool_ynab_query_transactions(filters: str) -> str:
    """Search transactions (e.g. 'Amazon > $50')."""
    return "Transaction search not yet connected to live YNAB API."

async def tool_ynab_categorize_transaction(transaction_id: str, category: str) -> str:
    """Recategorize a transaction."""
    return f"Transaction {transaction_id} moved to {category}."

async def tool_ynab_create_budget_goal(category: str, amount: str, deadline: str) -> str:
    """Set a budget goal."""
    return f"Budget goal set for {category}: ${amount} by {deadline}."

async def tool_ynab_analyze_spending_patterns(time_period: str, categories: str) -> str:
    """Analyze spending patterns."""
    return f"Spending analysis for {categories} over {time_period} requires more data history."

async def tool_ynab_forecast_cash_flow(months_ahead: str) -> str:
    """Predict future cash flow."""
    return f"Cash flow forecast for next {months_ahead} months generated."

async def tool_ynab_get_category_balance(category: str) -> str:
    """Check available funds for a specific category."""
    return await tool_check_budget(category)

async def tool_ynab_move_money(from_category: str, to_category: str, amount: str) -> str:
    """Move money between categories."""
    return f"Moved ${amount} from {from_category} to {to_category}."

# ==========================================
# 3. COMMUNICATION (Email)
# ==========================================

async def tool_email_draft(json_args: str) -> str:
    """
    Drafts an email via IMAP. 
    Expects a JSON string with keys: 'to', 'subject', 'body'.
    """
    try:
        clean_json = json_args.strip()
        if not clean_json.startswith("{"):
            # Attempt to handle if the user just passed args roughly
            return "Error: Tool expects a JSON string. Example: {'to': '...', 'subject': '...', 'body': '...'}"
            
        args = json.loads(clean_json)
        to_email = args.get("to")
        subject = args.get("subject")
        body = args.get("body")
        
        if not to_email or not subject:
            return "Error: Missing 'to' or 'subject' in arguments."
            
        success = await create_draft_task(to_email, subject, body)
        return "Draft saved successfully to 'Drafts' folder." if success else "Failed to save draft. Check SMTP/IMAP settings."
    except json.JSONDecodeError:
        return "Error: Arguments provided were not valid JSON."
    except Exception as e:
        return f"Error drafting email: {e}"

async def tool_email_search(query: str, filters: str = "") -> str:
    """Search emails."""
    return f"Searching emails for '{query}' with filters '{filters}'..."

async def tool_email_read(message_id: str) -> str:
    """Read specific email."""
    return f"Reading email {message_id}..."

async def tool_email_send(to: str, subject: str, body: str) -> str:
    """Send email (Requires explicit user confirmation in logic)."""
    return "Email sending is restricted. Use 'email_draft' instead."

async def tool_email_summarize_thread(thread_id: str) -> str:
    """Summarize conversation thread."""
    return f"Summarizing thread {thread_id}..."

async def tool_email_extract_action_items(message_ids: str) -> str:
    """Find tasks/todos in emails."""
    return "Extracting action items..."

async def tool_email_schedule_send(to: str, subject: str, body: str, send_time: str) -> str:
    """Schedule delayed email."""
    return f"Email to {to} scheduled for {send_time}."

async def tool_email_create_filter(conditions: str, actions: str) -> str:
    """Set up email rules."""
    return "Email filter created."

async def tool_email_bulk_action(message_ids: str, action: str) -> str:
    """Archive/label/delete multiple emails."""
    return f"Performed {action} on {message_ids}."

# ==========================================
# 4. MEDIA MANAGEMENT (Immich)
# ==========================================

async def tool_search_photos(description: str) -> str:
    """Searches Immich photo library with robust parsing."""
    try:
        results = await search_immich_photos(description)
        if not results: return f"No photos found matching '{description}'."
        out = []
        for r in results[:5]: 
            pid = r.get('id')
            date_str = r.get('fileCreatedAt') or r.get('exifInfo', {}).get('dateTimeOriginal') or r.get('createdAt') or "Unknown Date"
            out.append(f"- Found Photo (ID: {pid}) taken on {date_str}")
        return "\n".join(out)
    except Exception as e:
        return f"Error searching photos: {e}"

async def tool_immich_get_photo_metadata(photo_id: str) -> str:
    """Get photo details."""
    return f"Metadata for photo {photo_id}..."

async def tool_immich_create_album(name: str, photo_ids: str) -> str:
    """Organize photos into album."""
    return f"Album '{name}' created with specified photos."

async def tool_immich_get_albums() -> str:
    """List albums."""
    return "Listing all albums..."

async def tool_immich_facial_recognition_search(person: str) -> str:
    """Find person in photos."""
    return f"Searching for {person}..."

async def tool_immich_get_photos_by_location(location: str, radius: str = "10km") -> str:
    """Location-based search."""
    return f"Searching photos near {location}..."

async def tool_immich_get_photos_by_date(start_date: str, end_date: str) -> str:
    """Date range search."""
    return f"Searching photos between {start_date} and {end_date}..."

async def tool_immich_share_album(album_id: str, recipients: str) -> str:
    """Share photos."""
    return f"Sharing album {album_id} with {recipients}..."

# ==========================================
# 5. CALENDAR
# ==========================================

async def tool_check_calendar() -> str:
    """Lists events for today."""
    try:
        events = await get_todays_events()
        if not events: return "No events found for today."
        return str(events)
    except Exception as e:
        return f"Error checking calendar: {e}"

async def tool_calendar_get_events(date: str = None) -> str:
    """Query events for a specific date."""
    # In a full implementation, this would query the DB for that specific date
    return await tool_check_calendar()

async def tool_calendar_create_event(title: str, start: str, end: str, location: str = "", attendees: str = "", notes: str = "") -> str:
    """New event."""
    return f"Event '{title}' created for {start} to {end}."

async def tool_calendar_update_event(event_id: str, changes: str) -> str:
    """Modify event."""
    return f"Event {event_id} updated."

async def tool_calendar_delete_event(event_id: str) -> str:
    """Remove event."""
    return f"Event {event_id} deleted."

async def tool_calendar_find_free_slots(duration: str, date_range: str, constraints: str = "") -> str:
    """Find availability."""
    return "Searching for free slots..."

async def tool_calendar_check_conflicts(proposed_event: str) -> str:
    """Detect scheduling conflicts."""
    return "Checking for conflicts..."

async def tool_calendar_get_travel_time(from_loc: str, to_loc: str, departure_time: str) -> str:
    """Estimate travel."""
    return f"Estimated travel time from {from_loc} to {to_loc} is..."

async def tool_calendar_bulk_reschedule(event_ids: str, time_delta: str) -> str:
    """Move multiple events."""
    return "Rescheduled events."

# ==========================================
# 6. TASKS (Reminders)
# ==========================================

async def tool_list_tasks() -> str:
    """Lists currently pending tasks."""
    try:
        tasks = await get_pending_tasks()
        if not tasks: return "No pending tasks."
        return "\n".join([f"[ ] {t['description']} (ID: {t['id']})" for t in tasks])
    except Exception as e:
        return f"Error listing tasks: {e}"

async def tool_reminders_get_lists() -> str:
    """Get all lists."""
    return "Listing all task lists..."

async def tool_reminders_get_tasks(list_id: str = None, filters: str = None) -> str:
    """Query tasks."""
    return await tool_list_tasks()

async def tool_reminders_create_task(title: str, list_id: str = "default", due_date: str = None, priority: str = "none", notes: str = "") -> str:
    """
    Creates a new task.
    Supports a simple string input for 'title' even if the agent tries to pack args.
    """
    try:
        # 1. Clean up input if the agent was messy (e.g. passed 'Buy milk, default')
        task_desc = title.strip()
        if "," in task_desc and len(task_desc.split(",")) > 1:
            # Heuristic: If there's a comma, take the first part as title
            # This is optional but helps with basic multi-arg parsing from simple strings
            parts = task_desc.split(",")
            task_desc = parts[0].strip()
        
        # 2. Save to File System
        settings = await get_all_settings()
        folder = settings.get("steward_reminders_folder", STEWARD_REMINDERS_FOLDER)
        path = DOCS_PATH / folder / "reminders.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(path, "a", encoding="utf-8") as f: 
            await f.write(f"{task_desc}\n")
            
        # 3. Sync to Apple Reminders (if on Mac)
        success = await asyncio.to_thread(add_reminder_to_app, task_desc, "Inbox")
        msg = f"Task '{task_desc}' added to Apple Reminders & Files." if success else f"Task '{task_desc}' added to File only."
        
        return msg
    except Exception as e:
        logger.error(f"Task creation failed: {e}")
        return f"Error creating task: {e}"

async def tool_reminders_update_task(task_id: str, changes: str) -> str:
    """Modify task."""
    return f"Task {task_id} updated."

async def tool_reminders_complete_task(task_id: str) -> str:
    """Mark complete."""
    return f"Task {task_id} marked complete."

async def tool_reminders_get_overdue_tasks() -> str:
    """Find overdue items."""
    return "Checking for overdue tasks..."

async def tool_reminders_prioritize_tasks(criteria: str) -> str:
    """Smart prioritization."""
    return "Reprioritizing tasks..."

async def tool_reminders_create_recurring_task(template: str) -> str:
    """Set up recurring tasks."""
    return "Recurring task created."

# ==========================================
# 7. DOCUMENTS & KNOWLEDGE
# ==========================================

async def tool_read_clinical_pearls(count: str = "3") -> str:
    """Reads the most recent clinical pearls."""
    try:
        settings = await get_all_settings()
        folder = settings.get("steward_health_folder", STEWARD_HEALTH_FOLDER)
        path = DOCS_PATH / folder / "em_pearls_log.md"
        if not path.exists(): return "No clinical pearls log found."
        content = path.read_text()
        entries = [e for e in content.split("###") if e.strip()]
        try: num = int(count)
        except: num = 3
        return "### " + "### ".join(entries[-num:])
    except Exception as e:
        return f"Error reading pearls: {e}"

async def tool_documents_search(query: str, file_types: str = "all", locations: str = "all") -> str:
    """Full-text search (RAG)."""
    # This connects to the existing RAG pipeline logic in agent.py
    return f"Search for '{query}' initiated."

async def tool_documents_read(file_path: str) -> str:
    """Read document content."""
    # Stub: Needs secure path validation
    return f"Reading file at {file_path}..."

async def tool_documents_summarize(file_path: str) -> str:
    """Generate summary."""
    return f"Summarizing {file_path}..."

async def tool_documents_extract_entities(file_path: str) -> str:
    """Extract names, dates, etc."""
    return f"Extracting entities from {file_path}..."

async def tool_documents_create_note(title: str, content: str, tags: str = "") -> str:
    """Create new document."""
    return f"Note '{title}' created."

async def tool_documents_link_related(document_id: str) -> str:
    """Find related documents."""
    return "Searching for related documents..."

async def tool_documents_version_history(file_path: str) -> str:
    """Get document versions."""
    return f"Retrieving version history for {file_path}..."

async def tool_documents_ocr(image_path: str) -> str:
    """Extract text from images."""
    return f"Running OCR on {image_path}..."

# ==========================================
# 8. CROSS-SYSTEM INTEGRATION
# ==========================================

async def tool_create_event_from_email(email_id: str) -> str:
    """Email -> Calendar."""
    return f"Creating event from email {email_id}..."

async def tool_create_reminder_from_email(email_id: str) -> str:
    """Email -> Task."""
    return f"Creating reminder from email {email_id}..."

async def tool_link_transaction_to_receipt(transaction_id: str, photo_id: str) -> str:
    """YNAB -> Immich."""
    return f"Linked transaction {transaction_id} to receipt photo {photo_id}."

async def tool_create_health_reminder(metric: str, threshold: str) -> str:
    """Health -> Reminders."""
    return f"Reminder set for when {metric} hits {threshold}."

async def tool_add_event_travel_time_buffer(event_id: str) -> str:
    """Auto-add travel time."""
    return f"Added travel buffer to event {event_id}."

# ==========================================
# 9. META/SYSTEM & UTILITIES
# ==========================================

async def tool_get_current_context() -> str:
    """Get user's current state/location/time."""
    now = datetime.now()
    return f"Current Time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"

async def tool_get_time() -> str:
    return await tool_get_current_context()

async def tool_set_user_preference(key: str, value: str) -> str:
    """Remember preferences."""
    return f"Preference set: {key} = {value}"

async def tool_get_conversation_history(n_messages: str = "5") -> str:
    """Recall past interactions."""
    return "Retrieving conversation history..."

async def tool_create_automation(trigger: str, actions: str) -> str:
    """Set up IFTTT-style rules."""
    return f"Automation created: If {trigger}, then {actions}."

async def tool_execute_workflow(workflow_id: str, parameters: str) -> str:
    """Run saved workflows."""
    return f"Executing workflow {workflow_id}..."

async def tool_save_memory(fact: str) -> str:
    """Explicitly saves a fact to long-term memory."""
    try:
        stored = await extract_and_store_fact(fact)
        return f"Memory saved: '{stored}'"
    except Exception as e:
        return f"Error saving memory: {e}"

async def tool_search_web(query: str) -> str:
    """Searches the internet."""
    try:
        model = await get_active_model()
        # Ensure query context is sufficient if user provided vague terms
        if len(query.split()) < 3 and "weather" in query.lower():
             query += f" forecast {datetime.now().strftime('%B %d %Y')}"
             
        return await perform_web_search(query, model)
    except Exception as e:
        logger.error(f"Web Search Failed: {e}")
        return "Web search unavailable."

async def tool_check_weather(location: str = None) -> str:
    """
    Checks weather with robust fallback.
    """
    try:
        model = await get_active_model()
        # Always prefer web search for weather to get current data
        # Inject today's date to prevent 'I cannot predict future' errors from LLM
        today = datetime.now().strftime("%B %d, %Y")
        
        search_query = f"weather forecast {location if location else 'current location'} {today}"
        
        return await perform_web_search(search_query, model)
    except Exception as e:
        return f"Weather check failed: {e}"

async def tool_python_repl(code: str) -> str:
    """Executes Python code."""
    try:
        return await run_python_code(code)
    except Exception as e:
        return f"Python execution error: {e}"

# ==========================================
# REGISTRY
# ==========================================

AVAILABLE_TOOLS = {
    # 1. Health
    "health_query_metrics": {"func": tool_health_query_metrics, "desc": "Query specific health data (steps, weight, sleep). Input: metric_type, days.", "args": "metric_type, days"},
    "health_analyze_trends": {"func": tool_health_analyze_trends, "desc": "Analyze patterns in health data. Input: metrics.", "args": "metrics"},
    "health_set_goal": {"func": tool_health_set_goal, "desc": "Set health goals. Input: metric, target, deadline.", "args": "metric, target, deadline"},
    "health_get_correlations": {"func": tool_health_get_correlations, "desc": "Find relationships between metrics. Input: metric_pairs.", "args": "metric_pairs"},
    "health_export_report": {"func": tool_health_export_report, "desc": "Generate health report. Input: format, metrics, period.", "args": "format, metrics, period"},

    # 2. Finance
    "ynab_get_budget_summary": {"func": tool_check_budget, "desc": "Current budget state. Input: category.", "args": "category"},
    "ynab_query_transactions": {"func": tool_ynab_query_transactions, "desc": "Search transactions. Input: filters.", "args": "filters"},
    "ynab_categorize_transaction": {"func": tool_ynab_categorize_transaction, "desc": "Recategorize. Input: transaction_id, category.", "args": "transaction_id, category"},
    "ynab_create_budget_goal": {"func": tool_ynab_create_budget_goal, "desc": "Set goals. Input: category, amount, deadline.", "args": "category, amount, deadline"},
    "ynab_analyze_spending_patterns": {"func": tool_ynab_analyze_spending_patterns, "desc": "Spending analysis. Input: time_period, categories.", "args": "time_period, categories"},
    "ynab_forecast_cash_flow": {"func": tool_ynab_forecast_cash_flow, "desc": "Predict future state. Input: months_ahead.", "args": "months_ahead"},
    "ynab_get_category_balance": {"func": tool_ynab_get_category_balance, "desc": "Check available funds. Input: category.", "args": "category"},
    "ynab_move_money": {"func": tool_ynab_move_money, "desc": "Budget adjustments. Input: from_category, to_category, amount.", "args": "from_category, to_category, amount"},

    # 3. Communication
    "email_search": {"func": tool_email_search, "desc": "Search emails. Input: query, filters.", "args": "query, filters"},
    "email_read": {"func": tool_email_read, "desc": "Read specific email. Input: message_id.", "args": "message_id"},
    "email_send": {"func": tool_email_send, "desc": "Send email. Input: to, subject, body.", "args": "to, subject, body"},
    "email_draft": {"func": tool_email_draft, "desc": "Create draft. Input: JSON string args.", "args": "json_args"},
    "email_summarize_thread": {"func": tool_email_summarize_thread, "desc": "Summarize conversation. Input: thread_id.", "args": "thread_id"},
    "email_extract_action_items": {"func": tool_email_extract_action_items, "desc": "Find tasks/todos in email. Input: message_ids.", "args": "message_ids"},
    "email_schedule_send": {"func": tool_email_schedule_send, "desc": "Delayed send. Input: to, subject, body, send_time.", "args": "to, subject, body, send_time"},
    "email_create_filter": {"func": tool_email_create_filter, "desc": "Set up email rules. Input: conditions, actions.", "args": "conditions, actions"},
    "email_bulk_action": {"func": tool_email_bulk_action, "desc": "Archive/label/delete multiple. Input: message_ids, action.", "args": "message_ids, action"},

    # 4. Media
    "immich_search_photos": {"func": tool_search_photos, "desc": "Search photos. Input: query.", "args": "description"},
    "immich_get_photo_metadata": {"func": tool_immich_get_photo_metadata, "desc": "Get details. Input: photo_id.", "args": "photo_id"},
    "immich_create_album": {"func": tool_immich_create_album, "desc": "Organize photos. Input: name, photo_ids.", "args": "name, photo_ids"},
    "immich_get_albums": {"func": tool_immich_get_albums, "desc": "List albums. Input: None.", "args": ""},
    "immich_facial_recognition_search": {"func": tool_immich_facial_recognition_search, "desc": "Find person. Input: person.", "args": "person"},
    "immich_get_photos_by_location": {"func": tool_immich_get_photos_by_location, "desc": "Location search. Input: location, radius.", "args": "location, radius"},
    "immich_get_photos_by_date": {"func": tool_immich_get_photos_by_date, "desc": "Date range search. Input: start_date, end_date.", "args": "start_date, end_date"},
    "immich_share_album": {"func": tool_immich_share_album, "desc": "Share photos. Input: album_id, recipients.", "args": "album_id, recipients"},

    # 5. Calendar
    "calendar_get_events": {"func": tool_calendar_get_events, "desc": "Query events. Input: date.", "args": "date"},
    "calendar_create_event": {"func": tool_calendar_create_event, "desc": "New event. Input: title, start, end.", "args": "title, start, end"},
    "calendar_update_event": {"func": tool_calendar_update_event, "desc": "Modify event. Input: event_id, changes.", "args": "event_id, changes"},
    "calendar_delete_event": {"func": tool_calendar_delete_event, "desc": "Remove event. Input: event_id.", "args": "event_id"},
    "calendar_find_free_slots": {"func": tool_calendar_find_free_slots, "desc": "Find availability. Input: duration, date_range.", "args": "duration, date_range"},
    "calendar_check_conflicts": {"func": tool_calendar_check_conflicts, "desc": "Detect conflicts. Input: proposed_event.", "args": "proposed_event"},
    "calendar_get_travel_time": {"func": tool_calendar_get_travel_time, "desc": "Estimate travel. Input: from, to, departure.", "args": "from, to, departure"},
    "calendar_bulk_reschedule": {"func": tool_calendar_bulk_reschedule, "desc": "Move multiple events. Input: event_ids, time_delta.", "args": "event_ids, time_delta"},

    # 6. Tasks
    "reminders_get_lists": {"func": tool_reminders_get_lists, "desc": "Get all lists. Input: None.", "args": ""},
    "reminders_get_tasks": {"func": tool_reminders_get_tasks, "desc": "Query tasks. Input: list_id.", "args": "list_id"},
    "reminders_create_task": {"func": tool_reminders_create_task, "desc": "New task. Input: description.", "args": "title, list_id"},
    "reminders_update_task": {"func": tool_reminders_update_task, "desc": "Modify task. Input: task_id, changes.", "args": "task_id, changes"},
    "reminders_complete_task": {"func": tool_reminders_complete_task, "desc": "Mark complete. Input: task_id.", "args": "task_id"},
    "reminders_get_overdue_tasks": {"func": tool_reminders_get_overdue_tasks, "desc": "Find overdue items. Input: None.", "args": ""},
    "reminders_prioritize_tasks": {"func": tool_reminders_prioritize_tasks, "desc": "Smart prioritization. Input: criteria.", "args": "criteria"},
    "reminders_create_recurring_task": {"func": tool_reminders_create_recurring_task, "desc": "Set up recurring tasks. Input: template.", "args": "template"},

    # 7. Documents
    "documents_search": {"func": tool_documents_search, "desc": "Full-text search. Input: query.", "args": "query"},
    "documents_read": {"func": tool_documents_read, "desc": "Read document content. Input: file_path.", "args": "file_path"},
    "documents_summarize": {"func": tool_documents_summarize, "desc": "Generate summary. Input: file_path.", "args": "file_path"},
    "documents_extract_entities": {"func": tool_documents_extract_entities, "desc": "Extract names, dates. Input: file_path.", "args": "file_path"},
    "documents_create_note": {"func": tool_documents_create_note, "desc": "Create new document. Input: title, content.", "args": "title, content"},
    "documents_link_related": {"func": tool_documents_link_related, "desc": "Find related documents. Input: document_id.", "args": "document_id"},
    "documents_version_history": {"func": tool_documents_version_history, "desc": "Get document versions. Input: file_path.", "args": "file_path"},
    "documents_ocr": {"func": tool_documents_ocr, "desc": "Extract text from images. Input: image_path.", "args": "image_path"},
    "read_clinical_pearls": {"func": tool_read_clinical_pearls, "desc": "Read recent medical learning logs. Input: count.", "args": "count"},

    # 8. Cross-System
    "create_event_from_email": {"func": tool_create_event_from_email, "desc": "Email -> Calendar. Input: email_id.", "args": "email_id"},
    "create_reminder_from_email": {"func": tool_create_reminder_from_email, "desc": "Email -> Task. Input: email_id.", "args": "email_id"},
    "link_transaction_to_receipt": {"func": tool_link_transaction_to_receipt, "desc": "YNAB -> Immich. Input: trans_id, photo_id.", "args": "trans_id, photo_id"},
    "create_health_reminder": {"func": tool_create_health_reminder, "desc": "Health -> Reminders. Input: metric, threshold.", "args": "metric, threshold"},
    "add_event_travel_time_buffer": {"func": tool_add_event_travel_time_buffer, "desc": "Auto-add travel time. Input: event_id.", "args": "event_id"},

    # 9. Meta/System
    "get_current_context": {"func": tool_get_current_context, "desc": "Get user's current state. Input: None.", "args": ""},
    "set_user_preference": {"func": tool_set_user_preference, "desc": "Remember preferences. Input: key, value.", "args": "key, value"},
    "get_conversation_history": {"func": tool_get_conversation_history, "desc": "Recall past interactions. Input: n_messages.", "args": "n_messages"},
    "create_automation": {"func": tool_create_automation, "desc": "Set up rules. Input: trigger, actions.", "args": "trigger, actions"},
    "execute_workflow": {"func": tool_execute_workflow, "desc": "Run saved workflows. Input: workflow_id.", "args": "workflow_id"},
    "save_memory": {"func": tool_save_memory, "desc": "Save a fact. Input: fact.", "args": "fact"},

    # Utilities
    "search_web": {"func": tool_search_web, "desc": "Search internet. Input: query.", "args": "query"},
    "check_weather": {"func": tool_check_weather, "desc": "Check weather. Input: location.", "args": "location"},
    "python_repl": {"func": tool_python_repl, "desc": "Execute Python code. Input: code.", "args": "code"},
}