# backend/architecture/audit.py
import logging

logger = logging.getLogger(__name__)

class AuditLogger:
    @staticmethod
    def log_event(event_type: str, user_id: str, session_id: int, data: dict):
        """
        Logs structured events for compliance/debugging.
        """
        # In a production app, this might write to a separate audit.log or database.
        # For this local PWA, standard logging is sufficient.
        logger.info(f"📋 AUDIT [{event_type}] Session: {session_id} | Data: {data}")