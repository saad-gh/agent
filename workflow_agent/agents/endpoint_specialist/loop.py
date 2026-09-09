"""
Agent A Loop Controller (Endpoint Specialist).
"""
import logging
from typing import Dict, Any, Optional

from workflow_agent.agent_core.lifecycle import start_agent_plan
from workflow_agent.agent_core.registry import ToolRegistry
from .tools import endpoint_registry
from .prompt import ENDPOINT_SPECIALIST_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def run_endpoint_specialist(organization_id: int, prompt: str) -> Dict[str, Any]:
    """
    Execute Agent A turn to ingest docs and generate a standardized API spec.
    """
    logger.info(f"Running Agent A (Endpoint Specialist) for Org #{organization_id}: '{prompt[:60]}'")

    # Execute mock/live tool turn for Agent A
    from .tools import _handle_read_raw_doc, _handle_normalize_spec, _handle_upsert_api_spec

    # 1. Read raw doc
    doc_res = _handle_read_raw_doc({"service_name": "shopify"})

    # 2. Normalize spec
    sample_endpoints = [
        {
            "slug": "shopify_list_orders",
            "method": "GET",
            "path": "/admin/api/2024-01/orders.json",
            "summary": "Retrieve shopify orders",
            "params": [{"name": "status", "in": "query", "source": "{{ payload.status }}"}],
            "response": {"items_field": "orders", "pagination": {"type": "cursor", "next_field": "next_page_info"}},
            "auth": {"scopes": ["read_orders"]}
        },
        {
            "slug": "shopify_get_order_by_id",
            "method": "GET",
            "path": "/admin/api/2024-01/orders/{{ parent.response_json.order_id }}.json",
            "summary": "Retrieve specific order details",
            "params": [],
            "response": {"items_field": "order"},
            "auth": {"scopes": ["read_orders"]}
        }
    ]

    norm_res = _handle_normalize_spec({
        "service_name": "shopify",
        "version": "2024-01",
        "endpoints": sample_endpoints
    })

    # 3. Upsert API Spec
    upsert_res = _handle_upsert_api_spec({
        "service_name": "shopify",
        "spec_data": norm_res["spec_data"],
        "format": "yaml"
    })

    return {
        "agent": "endpoint_specialist",
        "organization_id": organization_id,
        "service": "shopify",
        "api_spec_path": upsert_res["api_spec_path"],
        "endpoints_count": upsert_res["endpoints_count"],
        "status": "completed"
    }
