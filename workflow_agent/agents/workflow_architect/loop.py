"""
Agent B Loop Controller (Workflow Architect).
"""
import logging
from typing import Dict, Any

from workflow_agent.agent_core.dsl import validate_plan_dsl
from workflow_agent.agent_core.materialize import _materialize_plan_dsl
from .tools import _handle_load_service_spec, _handle_submit_workflow_plan
from workflow_orchestrator.conf import get_organization_model

logger = logging.getLogger(__name__)


def run_workflow_architect(organization_id: int, service_name: str = "shopify") -> Dict[str, Any]:
    """
    Execute Agent B turn to read Service.api_spec_path and assemble a 5-array workflow plan.
    """
    logger.info(f"Running Agent B (Workflow Architect) for Org #{organization_id} on Service '{service_name}'")

    # 1. Load standardized spec created by Agent A
    spec_res = _handle_load_service_spec({"service_name": service_name})
    if spec_res.get("status") == "error":
        return spec_res

    endpoints = spec_res["spec_data"].get("endpoints", [])

    # 2. Build 5-array workflow plan from spec endpoints
    tasks = []
    workflows = []
    links = []

    for i, ep in enumerate(endpoints):
        slug = ep["slug"]
        tasks.append({
            "slug": slug,
            "name": ep.get("summary", slug),
            "task_type": "http",
            "attributes": {
                "method": ep["method"],
                "url": f"http://mock{ep['path']}"
            }
        })
        workflows.append({"task_slug": slug})
        if i > 0:
            links.append({
                "parent_task_slug": endpoints[i - 1]["slug"],
                "child_task_slug": slug
            })

    proposed_plan = {
        "tasks": tasks,
        "workflows": workflows,
        "workflow_links": links,
        "workflow_continuations": [],
        "task_continuations": []
    }

    # 3. Validate & Submit Plan
    submit_res = _handle_submit_workflow_plan({
        "organization_id": organization_id,
        "plan": proposed_plan
    })

    return {
        "agent": "workflow_architect",
        "organization_id": organization_id,
        "service": service_name,
        "api_spec_path": spec_res["api_spec_path"],
        "plan": proposed_plan,
        "materialized": submit_res.get("materialized"),
        "status": "completed"
    }
