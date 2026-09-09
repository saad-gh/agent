"""
Governance Agent Loop Controller.
"""
import logging
from typing import Dict, Any

from .policy import evaluate_action_policy
from .tools import _handle_approve_step
from workflow_agent.models import ManualStep, AgentRun
from workflow_orchestrator.conf import get_organization_model

logger = logging.getLogger(__name__)


def run_governance_agent(
    organization_id: int,
    action: str = "purchase",
    amount: float = 4050.00
) -> Dict[str, Any]:
    """
    Execute Governance Agent evaluation turn.
    """
    logger.info(f"Running Governance Agent for Org #{organization_id}: action='{action}', amount=${amount:,.2f}")

    decision = evaluate_action_policy(organization_id, action, amount)

    step_id = None
    if not decision.authorized:
        Organization = get_organization_model()
        org = Organization.objects.filter(id=organization_id).first()

        step = ManualStep.objects.create(
            organization=org,
            description=f"APPROVAL REQUIRED: {decision.reason}",
            status=ManualStep.STATUS_PENDING
        )
        step_id = step.id

    return {
        "agent": "governance",
        "organization_id": organization_id,
        "action": action,
        "amount": amount,
        "authorized": decision.authorized,
        "decision": decision.to_dict(),
        "manual_step_id": step_id,
        "status": "completed" if decision.authorized else "escalated_pending_approval"
    }
