# backend/email_tools.py
import imaplib
import smtplib
import email
from email.message import EmailMessage
import logging
import time
import asyncio
from backend.database import get_all_settings

logger = logging.getLogger(__name__)

# --- SENDING (SMTP) ---

def send_email_sync(server, port, user, password, to_email, subject, body_html):
    try:
        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content("Please enable HTML to view this message.")
        msg.add_alternative(body_html, subtype='html')

        with smtplib.SMTP(server, int(port)) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        
        logger.info(f"📧 Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False

async def send_clinical_alert(to_email: str, subject: str, content: str):
    """Sends a formatted clinical alert email."""
    settings = await get_all_settings()
    
    # Defaults for iCloud if not set, but prefer settings
    smtp_server = settings.get("smtp_server", "smtp.mail.me.com")
    smtp_port = settings.get("smtp_port", "587")
    smtp_user = settings.get("smtp_email", settings.get("imap_email"))
    smtp_pass = settings.get("smtp_password", settings.get("imap_password"))
    
    if not smtp_user or not smtp_pass:
        logger.warning("⚠️ Cannot send email: Missing SMTP credentials.")
        return False

    # Format HTML
    html_body = f"""
    <html>
    <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
        <div style="background: #f8f9fa; padding: 20px; border-left: 5px solid #007bff;">
            <h2 style="margin-top: 0;">ER Attending Update</h2>
            {content.replace(chr(10), '<br>')}
        </div>
        <p style="font-size: 0.8em; color: #666; margin-top: 20px;">
            AlsupOS Clinical Assistant • Automated Message
        </p>
    </body>
    </html>
    """
    
    return await asyncio.to_thread(
        send_email_sync, 
        smtp_server, 
        smtp_port, 
        smtp_user, 
        smtp_pass, 
        to_email, 
        subject, 
        html_body
    )

# --- DRAFTS (IMAP) ---

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
    settings = await get_all_settings()
    server = settings.get("imap_server")
    email_addr = settings.get("imap_email")
    password = settings.get("imap_password")
    
    if not server or not email_addr: return False
    
    return await asyncio.to_thread(save_draft_sync, server, email_addr, password, to, sub, body)