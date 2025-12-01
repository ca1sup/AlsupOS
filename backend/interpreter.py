# backend/interpreter.py
import logging
import io
import sys
import math
import datetime
import pandas as pd

logger = logging.getLogger(__name__)

SAFE_MODULES = {
    'math': math,
    'datetime': datetime,
    'pd': pd,
    'pandas': pd
}

async def run_python_code(code: str) -> str:
    """
    Executes Python code in a restricted namespace.
    Captures stdout.
    """
    # Remove dangerous builtins
    safe_builtins = {
        "print": print,
        "range": range,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "sum": sum,
        "max": max,
        "min": min,
        "round": round,
        "sorted": sorted
    }
    
    scope = {"__builtins__": safe_builtins, **SAFE_MODULES}
    
    # Capture stdout
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output
    
    try:
        # Strip markdown code blocks if present
        clean_code = code.replace("```python", "").replace("```", "").strip()
        
        exec(clean_code, scope)
        sys.stdout = old_stdout
        return redirected_output.getvalue() or "[No Output]"
    except Exception as e:
        sys.stdout = old_stdout
        return f"Error: {e}"