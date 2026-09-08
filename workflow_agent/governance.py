"""
Bounded Delegation & Governance Policy Engine.

Enforces user-defined organizational authority boundaries:
- Monetary spending limits for transactions
- Allowed vs restricted agent actions
- Discount/negotiation limits
- Automatic escalation to human approval when proposed actions exceed delegated authority
"""
import logging
from typing import Dict, Any, Optional, Tuple
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Default policy parameters if organization has no custom config
DEFAULT_DELEGATED_SPENDING_LIMIT = 5000.00  # $5,000 USD
DEFAULT_MAX_DISCOUNT_PERCENT = 15.0         # 15% max negotiation discount


class PolicyDecision:
    """Standardized policy evaluation outcome."""
    def __init__(
        self,
        authorized: bool,
        action: str,
        amount: float = 0.0,
        limit: float = DEFAULT_DELEGATED_SPENDING_LIMIT,
        reason: str = "",
        requires_approval: bool = False
    ):
        self.authorized = authorized
        self.action = action
        self.amount = amount
        self.limit = limit
        self.reason = reason
        self.requires_approval = requires_approval

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized": self.authorized,
            "action": self.action,
            "amount": self.amount,
            "limit": self.limit,
            "reason": self.reason,
            "requires_approval": self.requires_approval
        }


def get_organization_policy(organization_id: int) -> Dict[str, Any]:
    """
    Retrieve effective governance policy for an organization.
    Reads from Organization.metadata or defaults.
    """
    from workflow_orchestrator.conf import get_organization_model
    Organization = get_organization_model()

    org = Organization.objects.filter(id=organization_id).first()
    metadata = org.metadata if org and isinstance(org.metadata, dict) else {}

    policy = metadata.get('governance_policy', {})
    return {
        "delegated_spending_limit": float(policy.get('delegated_spending_limit', DEFAULT_DELEGATED_SPENDING_LIMIT)),
        "max_discount_percent": float(policy.get('max_discount_percent', DEFAULT_MAX_DISCOUNT_PERCENT)),
        "allowed_actions": policy.get('allowed_actions', [
            'search_suppliers', 'get_quote', 'purchase', 'negotiate',
            'list_services', 'read_api_docs'
        ]),
        "require_approval_above": float(policy.get('require_approval_above', DEFAULT_DELEGATED_SPENDING_LIMIT))
    }


def evaluate_action_policy(
    organization_id: int,
    action: str,
    amount: float = 0.0,
    params: Optional[Dict[str, Any]] = None
) -> PolicyDecision:
    """
    Evaluate whether a proposed agent action is authorized or requires escalation.

    Platform Security Principle:
    LLM proposes -> Policy engine validates -> Platform authorizes or escalates.
    The LLM is NOT the security authority.
    """
    policy = get_organization_policy(organization_id)
    spending_limit = policy["delegated_spending_limit"]
    allowed_actions = policy["allowed_actions"]

    # 1. Action Whitelist Check
    if action not in allowed_actions and f"action:{action}" not in allowed_actions:
        return PolicyDecision(
            authorized=False,
            action=action,
            amount=amount,
            limit=spending_limit,
            reason=f"Action '{action}' is not in allowed actions for Organization #{organization_id}.",
            requires_approval=True
        )

    # 2. Monetary Spending Limit Check
    if amount > 0.0 and amount > spending_limit:
        reason = (
            f"Action '{action}' with amount ${amount:,.2f} exceeds delegated authority limit "
            f"of ${spending_limit:,.2f}. Escalation to human principal required."
        )
        logger.info(f"[GOVERNANCE ESCALATION] Org #{organization_id}: {reason}")
        return PolicyDecision(
            authorized=False,
            action=action,
            amount=amount,
            limit=spending_limit,
            reason=reason,
            requires_approval=True
        )

    # 3. Negotiation Discount Check
    if action == "negotiate" and params:
        requested_discount = float(params.get('discount_percent', 0.0))
        max_discount = policy["max_discount_percent"]
        if requested_discount > max_discount:
            reason = (
                f"Requested discount of {requested_discount}% exceeds maximum allowed discount "
                f"limit of {max_discount}%."
            )
            return PolicyDecision(
                authorized=False,
                action=action,
                amount=amount,
                limit=max_discount,
                reason=reason,
                requires_approval=True
            )

    # Authorized
    return PolicyDecision(
        authorized=True,
        action=action,
        amount=amount,
        limit=spending_limit,
        reason=f"Action '{action}' within delegated authority limits.",
        requires_approval=False
    )


def guard_transaction_callable(ctx=None, **kwargs):
    """
    Python task entrypoint used as a WorkflowContinuation Gatekeeper.
    Evaluates policy before transaction execution.
    If over limit: declares ManualStep and returns skip signal to orchestrator.
    """
    if isinstance(ctx, dict):
        context = ctx.get('context')
        fn_kwargs = ctx.get('kwargs', {})
    else:
        context = None
        fn_kwargs = kwargs or {}

    org_id = getattr(context, 'org_id', None) or fn_kwargs.get('organization_id', 1)
    action = fn_kwargs.get('action', 'purchase')
    amount = float(fn_kwargs.get('amount') or fn_kwargs.get('total_price') or 0.0)

    # Check parent/context results if amount not directly in kwargs
    if amount == 0.0 and context:
        parent_res = context.parent_results[0] if context.parent_results else {}
        if isinstance(parent_res, dict):
            resp_json = parent_res.get('response_json', parent_res)
            if isinstance(resp_json, dict):
                amount = float(resp_json.get('total_price') or resp_json.get('amount') or 0.0)

    decision = evaluate_action_policy(org_id, action, amount, fn_kwargs)

    if not decision.authorized:
        # Create ManualStep for Human-in-the-loop escalation
        from .models import ManualStep, AgentRun
        from workflow_orchestrator.conf import get_organization_model
        Organization = get_organization_model()

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            org = Organization.objects.first()

        agent_run_id = getattr(context, 'agent_run_id', None)
        run_obj = AgentRun.objects.filter(id=agent_run_id).first() if agent_run_id else None

        step = ManualStep.objects.create(
            organization=org,
            agent_run=run_obj,
            description=f"APPROVAL REQUIRED: {decision.reason}",
            status=ManualStep.STATUS_PENDING
        )

        return {
            "_workflow_action": "skip",
            "status": "escalated_for_approval",
            "manual_step_id": step.id,
            "decision": decision.to_dict(),
            "message": "Transaction exceeds delegated authority. Escalated for human principal approval."
        }

    return {
        "status": "authorized",
        "decision": decision.to_dict(),
        "message": "Transaction authorized within delegated authority limits."
    }
