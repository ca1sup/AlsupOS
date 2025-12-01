import smtplib
import logging
from email.message import EmailMessage
from backend.database import get_all_settings

logger = logging.getLogger(__name__)

async def send_email(subject: str, body: str, recipient_email: str):
    """Existing SMTP Email Logic"""
    logger.info(f"Sending email to {recipient_email}...")
    try:
        settings = await get_all_settings()
        SMTP_SERVER = settings.get("smtp_server")
        SMTP_PORT = int(settings.get("smtp_port", 587))
        SENDER_EMAIL = settings.get("smtp_email")
        SENDER_PASSWORD = settings.get("smtp_password")

        if not all([SENDER_EMAIL, SMTP_SERVER, SENDER_PASSWORD]):
            logger.warning("SMTP settings incomplete. Skipping.")
            return

        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls() 
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        logger.info("Email sent.")
    except Exception as e:
        logger.error(f"Email Failed: {e}")

async def send_clinical_notification(title: str, body: str):
    """
    Sends a notification formatted for Clinical Aid.
    Currently logs to console, but ready for PyWebPush or APNS.
    """
    logger.info(f"🔔 CLINICAL ALERT: {title} \n{body}")
    
    # FUTURE: Implement pywebpush here
    # 1. Load VAPID keys from settings
    # 2. Fetch subscription info from DB
    # 3. webpush(subscription_info, data=body, vapid_private_key=...)
    
    # Fallback: Attempt email if configured
    settings = await get_all_settings()
    email = settings.get("smtp_email") # Send to self
    if email:
        await send_email(f"[ER AI] {title}", body, email)
