"""
Tools & ToolRegistry for Governance Agent.
"""
import logging
from typing import Dict, Any

from workflow_agent.agent_core.registry import ToolRegistry
from .policy import evaluate_action_policy, guard_transaction_callable
from workflow_agent.models import ManualStep

logger = logging.getLogger(__name__)

# Dedicated Tool Registry for Governance Agent
governance_registry = ToolRegistry("governance")


def _handle_check_policy(args: dict, context: Any = None) -> dict:
    org_id = args.get('organization_id') or getattr(context, 'org_id', 1)
    action = args.get('action', 'purchase')
    amount = float(args.get('amount', 0.0))

    decision = evaluate_action_policy(org_id, action, amount, args)
    return {
        "status": "success",
        "decision": decision.to_dict()
    }


def _handle_approve_step(args: dict, context: Any = None) -> dict:
    step_id = args.get('step_id')
    approved_by = args.get('approved_by', 'human_principal@apex.com')
    reason = args.get('reason', 'Approved by human principal')

    step = ManualStep.objects.filter(id=step_id).first()
    if not step:
        return {"status": "error", "error": f"ManualStep #{step_id} not found"}

    step.status = ManualStep.STATUS_DONE
    step.result_input = {"approved_by": approved_by, "reason": reason}
    step.save(update_fields=['status', 'result_input'])

    return {
        "status": "success",
        "step_id": step.id,
        "step_status": step.status,
        "approved_by": approved_by,
        "message": f"ManualStep #{step.id} successfully approved by human principal."
    }


# Register Governance Tools
governance_registry.register(
    {
        "name": "check_governance_policy",
        "description": "Evaluate action and monetary amount against organization spending authority limit.",
        "parameters": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "integer", "description": "Organization ID"},
                "action": {"type": "string", "description": "Action name"},
                "amount": {"type": "number", "description": "Monetary amount in USD"}
            },
            "required": ["action", "amount"]
        }
    },
    _handle_check_policy
)

governance_registry.register(
    {
        "name": "approve_escalated_step",
        "description": "Approve a pending human-in-the-loop ManualStep escalation.",
        "parameters": {
            "type": "object",
            "properties": {
                "step_id": {"type": "integer", "description": "ManualStep ID"},
                "approved_by": {"type": "string", "description": "Approver email/ID"},
                "reason": {"type": "string", "description": "Approval justification"}
            },
            "required": ["step_id"]
        }
    },
    _handle_approve_step
)
