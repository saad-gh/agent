"""
Generic Dynamic Tool Registry & Dispatcher Framework.

Enables each specialized agent app (Endpoint Specialist, Workflow Architect,
Governance Agent, Procurement Agent) to define, register, and dispatch its own
tools independently, replacing monolith global tool definitions.
"""
import json
import logging
from typing import Dict, Any, List, Callable, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Instance-based Tool Registry allowing individual agents to maintain isolated toolsets.
    """
    def __init__(self, name: str = "default"):
        self.name = name
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, definition: Dict[str, Any], handler: Callable) -> None:
        """Register a tool definition and its executable handler callable."""
        tool_name = definition.get("name")
        if not tool_name:
            raise ValueError("Tool definition must include a 'name' field")

        self._tools[tool_name] = definition
        self._handlers[tool_name] = handler
        logger.debug(f"Registered tool '{tool_name}' in ToolRegistry '{self.name}'")

    def get_definitions(self) -> List[Dict[str, Any]]:
        """Return list of JSON Schema tool definitions."""
        return [dict(t) for t in self._tools.values()]

    def dispatch(self, name: str, args: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """Dispatch a tool call to its registered handler callable."""
        handler = self._handlers.get(name)
        if not handler:
            return {"status": "error", "error": f"Unknown tool '{name}' in ToolRegistry '{self.name}'"}

        try:
            return handler(args, context)
        except Exception as e:
            logger.error(f"Error executing tool '{name}' in ToolRegistry '{self.name}': {e}", exc_info=True)
            return {"status": "error", "error": str(e)}


# Global Default Tool Registry instance for backward compatibility
_GLOBAL_REGISTRY = ToolRegistry("global_default")


def get_global_registry() -> ToolRegistry:
    return _GLOBAL_REGISTRY


# Populate global default registry from tools.py
def sync_global_registry_from_legacy():
    from workflow_agent.tools import TOOL_DEFINITIONS, _TOOL_HANDLERS
    for tool_def in TOOL_DEFINITIONS:
        tool_name = tool_def["name"]
        handler = _TOOL_HANDLERS.get(tool_name)
        if handler:
            _GLOBAL_REGISTRY.register(tool_def, handler)


# Initialize global registry bindings
try:
    sync_global_registry_from_legacy()
except Exception:
    pass
