"""
Tools & ToolRegistry for Agent B (Workflow Architect).
"""
import logging
from typing import Dict, Any, List

from workflow_agent.agent_core.registry import ToolRegistry
from workflow_agent.agent_core.spec import load_spec_for_service
from workflow_agent.agent_core.dsl import validate_plan_dsl
from workflow_agent.agent_core.materialize import _materialize_plan_dsl
from workflow_orchestrator.conf import get_service_model, get_organization_model

logger = logging.getLogger(__name__)

# Dedicated Tool Registry for Agent B
architect_registry = ToolRegistry("workflow_architect")


def _handle_list_service_specs(args: dict, context: Any = None) -> dict:
    Service = get_service_model()
    services = list(Service.objects.filter(is_active=True).values('id', 'name', 'api_spec_path', 'metadata'))
    return {
        "status": "success",
        "count": len(services),
        "services": services
    }


def _handle_load_service_spec(args: dict, context: Any = None) -> dict:
    service_name = args.get('service_name', '')
    Service = get_service_model()

    srv = Service.objects.filter(name__iexact=service_name).first()
    if not srv:
        return {"status": "error", "error": f"Service '{service_name}' not found"}

    if not srv.api_spec_path:
        return {"status": "error", "error": f"Service '{service_name}' has no api_spec_path configured yet by Agent A"}

    try:
        spec_data = load_spec_for_service(srv)
        return {
            "status": "success",
            "service": srv.name,
            "api_spec_path": srv.api_spec_path,
            "spec_data": spec_data
        }
    except Exception as e:
        logger.error(f"Error loading spec for service '{service_name}': {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def _handle_submit_workflow_plan(args: dict, context: Any = None) -> dict:
    plan = args.get('plan', {})
    organization_id = args.get('organization_id', 1)

    is_valid, err = validate_plan_dsl(plan)
    if not is_valid:
        return {"status": "error", "error": f"Plan DSL validation failed: {err}"}

    Organization = get_organization_model()
    org = Organization.objects.filter(id=organization_id).first()
    if not org:
        org = Organization.objects.first()

    summary = _materialize_plan_dsl(plan, org)
    return {
        "status": "success",
        "plan_valid": True,
        "materialized": summary,
        "message": "Workflow plan DSL successfully validated and materialized into orchestrator DB rows."
    }


# Register Tool Definitions
architect_registry.register(
    {
        "name": "list_service_specs",
        "description": "List all active SaaS services and their standardized API spec paths.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    _handle_list_service_specs
)

architect_registry.register(
    {
        "name": "load_service_spec",
        "description": "Read and parse the standardized API spec (YAML/JSON) for a service.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "SaaS service name (e.g. 'shopify')"}
            },
            "required": ["service_name"]
        }
    },
    _handle_load_service_spec
)

architect_registry.register(
    {
        "name": "submit_workflow_plan",
        "description": "Validate 5-array workflow plan DSL and materialize Task/Workflow DB rows.",
        "parameters": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "integer", "description": "Organization ID"},
                "plan": {"type": "object", "description": "5-array workflow plan dict"}
            },
            "required": ["plan"]
        }
    },
    _handle_submit_workflow_plan
)
