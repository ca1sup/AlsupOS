
# backend/med_news.py
import asyncio
import logging
import aiofiles
import httpx
import feedparser
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from backend.database import get_all_settings, init_db
from backend.rag import get_ai_response
from backend.config import DOCS_PATH, STEWARD_HEALTH_FOLDER

logger = logging.getLogger(__name__)

def _clean_html(html_content: str) -> str:
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return " ".join(text.split()[:1500])
    except Exception: return html_content

async def _get_article_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return _clean_html(response.text)
    except: return ""

async def _process_feed_group(
    feed_urls_json: str, 
    prompt_template: str, 
    folder_name: str, 
    file_name: str,
    lookback_days: int = 2
):
    """
    Generic processor for a group of RSS feeds (e.g. Medical or General).
    """
    if not feed_urls_json: return

    try: 
        feed_urls = json.loads(feed_urls_json)
        if not isinstance(feed_urls, list): return
    except: return

    cutoff = datetime.now() - timedelta(days=lookback_days)
    new_articles = []

    # 1. Fetch from all feeds
    for url in feed_urls:
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            for entry in feed.entries:
                # Parse date (handle various formats)
                dt = datetime.now()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    dt = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    dt = datetime(*entry.updated_parsed[:6])
                
                if dt > cutoff:
                    new_articles.append(entry)
                    # Limit to 1 article per feed to avoid blasting API
                    break 
        except Exception as e:
            logger.warning(f"Failed to parse feed {url}: {e}")

    if not new_articles:
        return

    # 2. Summarize each
    summary_output = ""
    for article in new_articles:
        try:
            text = await _get_article_text(article.link)
            if not text: continue
            
            # Contextual Prompt
            sys_msg = "You are a helpful news assistant."
            user_msg = f"{prompt_template}\n\nTITLE: {article.title}\nCONTENT: {text}"
            
            summary = await get_ai_response([
                {"role": "system", "content": sys_msg}, 
                {"role": "user", "content": user_msg}
            ])
            
            summary_output += f"### {datetime.now().date()} - {article.title}\n{summary}\n\n"
        except Exception as e:
            logger.error(f"Failed to summarize article {article.link}: {e}")

    # 3. Save to File
    if summary_output:
        output_path = DOCS_PATH / folder_name
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / file_name
        
        async with aiofiles.open(output_file, "a") as f:
            await f.write(summary_output)

async def run_med_news_sync():
    """
    Syncs both Emergency Medicine Pearls AND General News.
    """
    logger.info("--- Running News Sync ---")
    try:
        await init_db()
        settings = await get_all_settings()
        
        health_folder = settings.get("steward_health_folder", STEWARD_HEALTH_FOLDER)
        
        # --- 1. Medical Pearls ---
        med_feeds = settings.get("em_rss_feeds")
        med_prompt = settings.get("med_news_summary_prompt", "Summarize into a single, high-yield clinical pearl for an Emergency Medicine physician.")
        await _process_feed_group(med_feeds, med_prompt, health_folder, "em_pearls_log.md")
        
        # --- 2. General News ---
        gen_feeds = settings.get("general_rss_feeds") # New Setting
        gen_prompt = settings.get("general_news_summary_prompt", "Summarize this news article into a 2-3 sentence executive summary for a daily briefing.")
        await _process_feed_group(gen_feeds, gen_prompt, "Steward_News", "general_news_log.md")
            
    except Exception as e:
        logger.error(f"News Sync Failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(run_med_news_sync())