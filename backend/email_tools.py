# backend/email_tools.py
import imaplib
import email
from email.message import EmailMessage
import logging
import time
from backend.database import get_all_settings

logger = logging.getLogger(__name__)

def save_draft(to_email: str, subject: str, body: str) -> bool:
    """
    Connects to IMAP and appends a message to the Drafts folder.
    """
    try:
        # Run sync code in thread context usually, but strictly defined here
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # This function is intended to be run via asyncio.to_thread
        except: pass
        
        # We need to fetch settings. Since this runs in a thread, we need a new loop or pass args.
        # For simplicity in this architecture, we will assume settings are passed or use a sync DB accessor if needed.
        # Ideally, the caller passes the credentials.
        return False # Placeholder if not called correctly via main wrapper
    except: return False

def save_draft_sync(server, email_addr, password, to_email, subject, body):
    try:
        msg = EmailMessage()
        msg["From"] = email_addr
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        
        mail = imaplib.IMAP4_SSL(server)
        mail.login(email_addr, password)
        
        draft_box = None
        for box in ["Drafts", "Draft", "[Gmail]/Drafts", "INBOX.Drafts"]:
            try:
                status, _ = mail.select(box)
                if status == "OK":
                    draft_box = box
                    break
            except: pass
            
        if not draft_box:
            mail.logout()
            return False

        mail.append(draft_box, '\\Draft', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        mail.logout()
        return True
    except Exception as e:
        logger.error(f"Draft Save Error: {e}")
        return False

async def create_draft_task(to: str, sub: str, body: str):
    import asyncio
    settings = await get_all_settings()
    server = settings.get("imap_server")
    email_addr = settings.get("imap_email")
    password = settings.get("imap_password")
    
    if not server or not email_addr: return False
    
    return await asyncio.to_thread(save_draft_sync, server, email_addr, password, to, sub, body)