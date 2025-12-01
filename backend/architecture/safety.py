# backend/architecture/safety.py
import logging

logger = logging.getLogger(__name__)

class SafetyPolicy:
    @staticmethod
    def check_tool_safety(tool_name: str, tool_args: dict) -> dict:
        """
        Checks if a tool execution is safe.
        Returns: {"requires_confirmation": bool, "reason": str}
        """
        # Define high-stakes tools that might require user approval
        # For now, most read-only tools are safe.
        
        # Example of logic you could enable later:
        # if tool_name == "email_send" and "all" in tool_args.get("to", ""):
        #     return {"requires_confirmation": True, "reason": "Mass email detected"}
        
        return {"requires_confirmation": False, "reason": "Tool is allowed by default policy"}