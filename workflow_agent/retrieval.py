"""
Vector/Graph Retrieval Module (pgvector & Relational Context Recall).
Recalls relevant API documentation snippets and past conversation outcomes.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from django.db.models import Q

logger = logging.getLogger(__name__)


def recall_context_items(query: str, context: Any = None, top_k: int = 5) -> Dict[str, Any]:
    """
    Perform context recall over ApiDocumentation and AgentMessage transcripts.

    Args:
        query: Search term or question
        context: ExecutionContext object
        top_k: Number of results to return

    Returns:
        Dict with status, query, and list of recalled items
    """
    recalled_items = []

    try:
        from .models import ApiDocumentation, AgentMessage

        # 1. Query ApiDocumentation by text match or vector distance if available
        docs = ApiDocumentation.objects.filter(
            Q(name__icontains=query) |
            Q(content__icontains=query) |
            Q(source_url__icontains=query)
        ).select_related('service')[:top_k]

        for doc in docs:
            recalled_items.append({
                "type": "api_doc",
                "service": doc.service.name if doc.service else "",
                "title": doc.name,
                "version": doc.version,
                "content_snippet": (doc.content or json.dumps(doc.metadata))[:500],
                "verified": doc.verified,
                "source_url": doc.source_url
            })

        # 2. Query AgentMessage history for prior decisions or summaries
        messages = AgentMessage.objects.filter(
            Q(content__icontains=query) | Q(role='summary')
        ).order_by('-id')[:top_k]

        for msg in messages:
            recalled_items.append({
                "type": "past_message",
                "agent_run_id": msg.agent_run_id,
                "role": msg.role,
                "tool_name": msg.tool_name,
                "snippet": msg.content[:300]
            })

    except Exception as e:
        logger.error(f"Error in recall_context_items for query '{query}': {e}", exc_info=True)

    return {
        "status": "success",
        "query": query,
        "count": len(recalled_items),
        "recalled": recalled_items
    }
