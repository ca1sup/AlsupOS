import smtplib
import logging
import asyncio
from email.message import EmailMessage
from backend.database import get_all_settings

logger = logging.getLogger(__name__)

def _send_email_sync(server_addr, port, user, password, subject, body, recipient_email):
    """
    Synchronous SMTP sending logic, designed to be run in a thread.
    """
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = user
        msg['To'] = recipient_email

        # Standard SMTP context manager handles quit/close
        with smtplib.SMTP(server_addr, port) as server:
            server.starttls() 
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"SMTP Sync Error: {e}")
        raise e

async def send_email(subject: str, body: str, recipient_email: str):
    """
    Sends an email using configured SMTP settings.
    Non-blocking: Offloads the blocking SMTP call to a separate thread.
    """
    logger.info(f"Processing email to {recipient_email}...")
    try:
        settings = await get_all_settings()
        SMTP_SERVER = settings.get("smtp_server")
        try:
            SMTP_PORT = int(settings.get("smtp_port", 587))
        except:
            SMTP_PORT = 587
        SENDER_EMAIL = settings.get("smtp_email")
        SENDER_PASSWORD = settings.get("smtp_password")

        if not all([SENDER_EMAIL, SMTP_SERVER, SENDER_PASSWORD]):
            logger.warning("SMTP settings incomplete. Skipping email.")
            return

        # Run blocking SMTP call in a separate thread so the main loop doesn't freeze
        await asyncio.to_thread(
            _send_email_sync,
            SMTP_SERVER,
            SMTP_PORT,
            SENDER_EMAIL,
            SENDER_PASSWORD,
            subject,
            body,
            recipient_email
        )
        logger.info("Email sent successfully.")
    except Exception as e:
        logger.error(f"Email Failed: {e}")

async def send_clinical_notification(title: str, body: str):
    """
    Sends a notification formatted for Clinical Aid.
    """
    logger.info(f"🔔 CLINICAL ALERT: {title} \n{body}")
    
    # Fallback: Attempt email if configured
    settings = await get_all_settings()
    
    # Use dedicated recipient if available, otherwise send to self
    email = settings.get("recipient_email_chris") or settings.get("smtp_email")
    
    if email and settings.get("module_email_enabled", "false") == "true":
        await send_email(f"[ER AI] {title}", body, email)