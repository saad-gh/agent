"""
Agent Core LLM Provider Abstraction Module.

Unified completion interface dispatching to OpenAI, Anthropic, Google Gemini,
or offline Mock provider based on Model Resource metadata.
Also provides estimate_cost for token usage calculation.
"""
from workflow_agent.llm_client import (
    complete,
    _extract_metadata,
    _resolve_api_key,
    _mock_complete,
    _openai_complete,
    _anthropic_complete,
    _google_complete
)
from workflow_agent.cost import estimate_cost

__all__ = [
    'complete',
    'estimate_cost',
    '_extract_metadata',
    '_resolve_api_key',
    '_mock_complete',
    '_openai_complete',
    '_anthropic_complete',
    '_google_complete'
]
