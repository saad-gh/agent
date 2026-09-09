"""
Tools & ToolRegistry for Agent A (Endpoint Specialist).
"""
import json
import logging
from typing import Dict, Any, List

from workflow_agent.agent_core.registry import ToolRegistry
from workflow_agent.agent_core.security import fetch_url_safe
from workflow_agent.agent_core.spec import save_spec_for_service, validate_api_spec
from workflow_orchestrator.conf import get_service_model

logger = logging.getLogger(__name__)

# Dedicated Tool Registry for Agent A
endpoint_registry = ToolRegistry("endpoint_specialist")


def _handle_read_raw_doc(args: dict, context: Any = None) -> dict:
    service_name = args.get('service_name', '')
    url = args.get('url', '')

    if url:
        return fetch_url_safe(url)

    if service_name:
        from workflow_agent.models import ApiDocumentation
        Service = get_service_model()
        srv = Service.objects.filter(name__iexact=service_name).first()
        if not srv:
            return {"status": "error", "error": f"Service '{service_name}' not found"}

        doc = ApiDocumentation.objects.filter(service=srv, is_latest=True).first()
        if not doc:
            return {"status": "error", "error": f"No raw ApiDocumentation found for service '{service_name}'"}

        return {
            "status": "success",
            "service": srv.name,
            "version": doc.version,
            "content": doc.content[:10000]
        }

    return {"status": "error", "error": "Either service_name or url must be provided"}


def _handle_normalize_spec(args: dict, context: Any = None) -> dict:
    service_name = args.get('service_name', '')
    version = args.get('version', 'v1')
    endpoints = args.get('endpoints', [])

    spec_data = {
        "service": service_name,
        "version": version,
        "endpoints": endpoints
    }

    is_valid, err = validate_api_spec(spec_data)
    if not is_valid:
        return {"status": "error", "error": f"Spec normalization validation failed: {err}"}

    return {
        "status": "success",
        "spec_data": spec_data,
        "message": f"Successfully normalized spec for '{service_name}' with {len(endpoints)} endpoints."
    }


def _handle_upsert_api_spec(args: dict, context: Any = None) -> dict:
    service_name = args.get('service_name', '')
    spec_data = args.get('spec_data', {})
    fmt = args.get('format', 'yaml')

    if not spec_data and args.get('endpoints'):
        spec_data = {
            "service": service_name,
            "version": args.get('version', 'v1'),
            "endpoints": args.get('endpoints', [])
        }

    Service = get_service_model()
    srv, _ = Service.objects.get_or_create(name=service_name.lower())

    try:
        saved_path = save_spec_for_service(srv, spec_data, fmt=fmt)
        return {
            "status": "success",
            "service": srv.name,
            "api_spec_path": saved_path,
            "endpoints_count": len(spec_data.get('endpoints', [])),
            "message": f"API spec successfully written to '{saved_path}' and bound to Service '{srv.name}'."
        }
    except Exception as e:
        logger.error(f"Error in upsert_api_spec for '{service_name}': {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# Register Tool Definitions
endpoint_registry.register(
    {
        "name": "read_raw_doc",
        "description": "Read raw API documentation or fetch OpenAPI specs from URL or DB.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "SaaS service name"},
                "url": {"type": "string", "description": "Optional absolute URL to fetch"}
            }
        }
    },
    _handle_read_raw_doc
)

endpoint_registry.register(
    {
        "name": "normalize_spec",
        "description": "Transform parsed API documentation into standardized spec format.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Service name"},
                "version": {"type": "string", "description": "API version"},
                "endpoints": {"type": "array", "items": {"type": "object"}, "description": "Endpoint definitions"}
            },
            "required": ["service_name", "endpoints"]
        }
    },
    _handle_normalize_spec
)

endpoint_registry.register(
    {
        "name": "upsert_api_spec",
        "description": "Validate and write standardized API spec to storage and update Service.api_spec_path.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Target service name"},
                "spec_data": {"type": "object", "description": "Standardized spec dict"},
                "format": {"type": "string", "description": "Format: yaml or json"}
            },
            "required": ["service_name"]
        }
    },
    _handle_upsert_api_spec
)
