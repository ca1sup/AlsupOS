# backend/agent_orchestrator.py
import json
import logging
import asyncio
from typing import AsyncGenerator

from backend.database import get_all_settings
from backend.rag import get_ai_response, get_ai_response_stream
from backend.tools import AVAILABLE_TOOLS
from backend.architecture.audit import AuditLogger
from backend.architecture.safety import SafetyPolicy

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self, session_id: int, user_id: str = "chris_alsup"):
        self.session_id = session_id
        self.user_id = user_id
        self.model = "phi4-mini" # Default, updated in run

    async def run(self, query: str) -> AsyncGenerator[str, None]:
        """
        Main entry point for the Agentic Loop.
        """
        settings = await get_all_settings()
        self.model = settings.get("llm_model", "phi4-mini")
        
        AuditLogger.log_event("USER_REQUEST", self.user_id, self.session_id, {"query": query})
        
        yield "Orchestrating plan...\n\n"

        # 1. PLAN
        plan = await self._generate_plan(query)
        yield f"📝 Plan generated: {len(plan)} steps.\n"
        
        # 2. EXECUTE LOOP
        results = []
        for step in plan:
            tool_name = step.get("tool")
            tool_args = step.get("arg", "")
            
            # Safety Check
            safety = SafetyPolicy.check_tool_safety(tool_name, {}) # Args parsing needed for deep check
            
            if safety["requires_confirmation"]:
                yield f" **APPROVAL REQUIRED:** I want to run `{tool_name}`. Waiting for confirmation... (Auto-skipped for now)\n"
                AuditLogger.log_event("TOOL_BLOCKED", self.user_id, self.session_id, {"tool": tool_name, "reason": safety["reason"]})
                results.append(f"Tool {tool_name} BLOCKED by Safety Policy.")
                continue

            yield f"🛠️ Executing: {tool_name}...\n"
            
            try:
                result = await self._execute_tool(tool_name, tool_args)
                results.append(f"--- {tool_name} Result ---\n{result}")
                AuditLogger.log_event("TOOL_SUCCESS", self.user_id, self.session_id, {"tool": tool_name, "result_len": len(str(result))})
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                results.append(f"--- {tool_name} Failed ---\n{error_msg}")
                AuditLogger.log_event("TOOL_ERROR", self.user_id, self.session_id, {"tool": tool_name, "error": error_msg})
                yield f"❌ Tool failed: {error_msg}\n"

        # 3. SYNTHESIZE
        yield "\n💡 Synthesizing result...\n\n"
        async for token in self._synthesize_answer(query, results):
            yield token

    async def _generate_plan(self, query: str) -> list:
        """
        Uses LLM to generate a JSON list of steps.
        """
        tools_desc = "\n".join([f"- {k}: {v['desc']}" for k, v in AVAILABLE_TOOLS.items()])
        
        system_prompt = f"""You are the Planner.
Available Tools:
{tools_desc}

Task: Create a sequential plan to answer: "{query}"
Return strictly a JSON list of objects: [{{"tool": "name", "arg": "value"}}]
"""
        try:
            response = await get_ai_response([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Make the plan."}
            ], model=self.model)
            
            # Clean JSON
            clean = response.strip().replace("```json", "").replace("```", "")
            return json.loads(clean)
        except:
            return [] # Fallback

    async def _execute_tool(self, name: str, arg: str):
        if name not in AVAILABLE_TOOLS:
            raise ValueError(f"Tool {name} not found")
        
        tool_def = AVAILABLE_TOOLS[name]
        func = tool_def["func"]
        
        # Handle arg mapping simplisticly for now
        if tool_def["args"]:
            return await func(arg)
        else:
            return await func()

    async def _synthesize_answer(self, query: str, tool_outputs: list) -> AsyncGenerator[str, None]:
        context = "\n\n".join(tool_outputs)
        sys_prompt = "You are Steward. Answer the user based on the tool outputs below."
        
        async for token in get_ai_response_stream(query, [context], [], "Steward"):
            yield token