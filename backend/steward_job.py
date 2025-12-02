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

        # 1. Gather Context
        current_date_str = datetime.now().strftime("%A, %B %d")
        todays_events_str = await get_todays_events()
        tasks = await get_pending_tasks()
        tasks_str = "\n".join([f"- {t['description']}" for t in tasks]) if tasks else "No pending tasks."
        
        try:
            completed_tasks = get_recently_completed_reminders()
            completed_str = "\n".join([f"- {t}" for t in completed_tasks]) if completed_tasks else "None."
        except: completed_str = "Error."

        journal_context = await get_recent_journals_content(days=2)
        health = await get_recent_health_metrics_structured(days=1)
        health_str = str(health[0]) if health else "No recent health data."
        facts = await get_all_user_facts()
        facts_str = "\n".join([f"- {f}" for f in facts])

        weeks_events = await get_weeks_events_structured()
        weeks_str = "\n".join([f"- {e['title']} ({e['start_time']})" for e in weeks_events])

        # 2. Construct Prompt using Settings
        template = settings.get("steward_daily_prompt_template") or """
        You are my steward. It is {current_date}.
        Events: {todays_events}
        Tasks: {tasks}
        Health: {health_summary}
        Journal: {recent_journals}
        Please summarize my day and suggest improvements.
        """
        
        # Robust formatting: provide all potential keys
        prompt = template.format(
            current_date=current_date_str,
            todays_events=todays_events_str,
            weeks_events=weeks_str,
            tasks=tasks_str,
            completed=completed_str,
            recent_journals=journal_context,
            health_summary=health_str,
            family_context=facts_str, 
            
            # FIX: Added 'all_context' to resolve previous KeyError
            all_context=f"Events: {todays_events_str}\nTasks: {tasks_str}\nHealth: {health_str}\nFacts: {facts_str}",

            # Fill placeholders if they exist in the template but not calculated here
            finance_summary="Finance sync pending",
            workout_plan="Workout pending",
            worship_plan="Worship pending",
            homeschool_plan="Homeschool pending",
            clinical_pearl="No pearl today",
            months_events="",
            
            # FIX: Added missing keys for robustness (risk_analysis_output error)
            risk_analysis_output="No specific risk analysis generated.",
            project_updates="No active project updates."
        )

        # 3. Generate
        response = await get_ai_response([
            {"role": "system", "content": settings.get("system_prompt", "You are a helpful steward.")},
            {"role": "user", "content": prompt}
        ])

        # 4. Save
        await save_suggestion(response, response) 
        logger.info("Daily Summary Generated.")

    except Exception as e:
        logger.error(f"Daily Summary Failed: {e}", exc_info=True)