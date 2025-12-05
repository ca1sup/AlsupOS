import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database import (
    get_all_settings,
    get_recent_health_metrics_structured,
    get_recent_journals_content,
    get_todays_events,
    get_weeks_events_structured,
    get_pending_tasks,
    get_all_user_facts,
    save_suggestion,
    get_most_recent_workout_date_and_exercises
)
from backend.rag import get_ai_response
from backend.apple_actions import get_recently_completed_reminders
from backend.prompts import STEWARD_USER_PROMPT_TEMPLATE
from backend.notifications import send_email
from backend.weather import get_current_weather

logger = logging.getLogger(__name__)

class StewardJob:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(run_daily_summary, 'cron', hour=3, minute=0, id='daily_summary_job', replace_existing=True)
        if not self.scheduler.running: self.scheduler.start()

    def stop(self):
        if self.scheduler.running: self.scheduler.shutdown()

# --- Daily Summary Task ---

async def run_daily_summary():
    logger.info("Running Steward Daily Job...")
    try:
        settings = await get_all_settings()
        if settings.get("steward_enabled", "true") != "true": return

        # 1. Gather Definite Context
        current_date_str = datetime.now().strftime("%A, %B %d")
        
        # Weather
        weather_str = await get_current_weather()
        
        todays_events_str = await get_todays_events()
        weeks_events = await get_weeks_events_structured()
        weeks_str = "\n".join([f"- {e['title']} ({e['start_time']})" for e in weeks_events])
        
        tasks = await get_pending_tasks()
        tasks_str = "\n".join([f"- {t['description']}" for t in tasks]) if tasks else "No pending tasks."
        
        try:
            completed_tasks = get_recently_completed_reminders()
            completed_str = "\n".join([f"- {t}" for t in completed_tasks]) if completed_tasks else "None."
        except: completed_str = "Unavailable"

        journal_context = await get_recent_journals_content(days=2)
        health = await get_recent_health_metrics_structured(days=1)
        health_str = str(health[0]) if health else "No recent health data."
        
        facts = await get_all_user_facts()
        facts_str = "\n".join([f"- {f}" for f in facts])

        # 2. Definite Data Dictionary
        context_data = {
            "current_date": current_date_str,
            "weather_summary": weather_str,
            "todays_events": todays_events_str,
            "weeks_events": weeks_str,
            "tasks": tasks_str,
            "completed": completed_str,
            "recent_journals": journal_context,
            "health_summary": health_str,
            "family_context": facts_str,
            
            # Aggregate variable for custom templates
            "all_context": f"""
            --- AGGREGATED CONTEXT ---
            WEATHER: {weather_str}
            CALENDAR: {todays_events_str}
            TASKS: {tasks_str}
            HEALTH: {health_str}
            FACTS: {facts_str}
            """
        }

        # 3. Format with Fallback
        db_template = settings.get("steward_daily_prompt_template")
        prompt = ""
        
        if db_template:
            try:
                prompt = db_template.format(**context_data)
            except KeyError as e:
                logger.warning(f"⚠️ Custom/DB template failed: {e}. Falling back to default.")
                prompt = STEWARD_USER_PROMPT_TEMPLATE.format(**context_data)
        else:
            prompt = STEWARD_USER_PROMPT_TEMPLATE.format(**context_data)

        # 4. Generate
        response = await get_ai_response([
            {"role": "system", "content": settings.get("system_prompt", "You are a helpful steward.")},
            {"role": "user", "content": prompt}
        ])

        # 5. Save
        await save_suggestion(response, response) 
        logger.info("Daily Summary Generated.")

        # 6. Email Dispatch
        if settings.get("module_email_enabled", "false") == "true":
            recipient = settings.get("recipient_email_chris") or settings.get("smtp_email")
            if recipient:
                subject = f"Daily Briefing | {current_date_str}"
                logger.info(f"📧 Queueing briefing email to {recipient}...")
                await send_email(subject, response, recipient)
            else:
                logger.warning("Daily Briefing skipped: Email module enabled but no recipient configured.")

    except Exception as e:
        logger.error(f"Daily Summary Failed: {e}", exc_info=True)