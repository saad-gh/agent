"""
Tools & ToolRegistry for Procurement Agent.
"""
import logging
from typing import Dict, Any

from workflow_agent.agent_core.registry import ToolRegistry
from workflow_agent.tools import _handle_search_suppliers, _handle_get_quote, _handle_check_governance_policy

logger = logging.getLogger(__name__)

# Dedicated Tool Registry for Procurement Agent
procurement_registry = ToolRegistry("procurement")


def _handle_execute_purchase(args: dict, context: Any = None) -> dict:
    org_id = args.get('organization_id', 1)
    quote_id = args.get('quote_id', 'QT-SUP-001-8821')
    amount = float(args.get('amount', 4050.00))

    from workflow_agent.agents.governance.policy import evaluate_action_policy
    decision = evaluate_action_policy(org_id, "purchase", amount)

    if not decision.authorized:
        return {
            "status": "error",
            "escalated": True,
            "reason": decision.reason,
            "message": f"Purchase for quote '{quote_id}' (${amount:,.2f}) exceeds delegated limit of ${decision.limit:,.2f}."
        }

    return {
        "status": "success",
        "quote_id": quote_id,
        "amount_charged_usd": amount,
        "transaction_id": f"TX-PROC-{quote_id.replace('QT-', '')}",
        "delivery_eta": "2026-09-15",
        "message": f"Purchase for quote '{quote_id}' (${amount:,.2f}) successfully executed."
    }


# Register Procurement Tools
procurement_registry.register(
    {
        "name": "search_suppliers",
        "description": "Search qualified component/product suppliers for procurement.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Item specifications"},
                "quantity": {"type": "integer", "description": "Quantity required"}
            },
            "required": ["item_name", "quantity"]
        }
    },
    _handle_search_suppliers
)

procurement_registry.register(
    {
        "name": "get_quote",
        "description": "Obtain quotation with target negotiation discount from supplier.",
        "parameters": {
            "type": "object",
            "properties": {
                "supplier_id": {"type": "string", "description": "Supplier ID"},
                "item_name": {"type": "string", "description": "Item name"},
                "quantity": {"type": "integer", "description": "Quantity"},
                "target_discount_pct": {"type": "number", "description": "Target discount %"}
            },
            "required": ["supplier_id", "quantity"]
        }
    },
    _handle_get_quote
)

procurement_registry.register(
    {
        "name": "check_governance_policy",
        "description": "Evaluate proposed transaction against organization delegated limit.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action name"},
                "amount": {"type": "number", "description": "Amount in USD"}
            },
            "required": ["action", "amount"]
        }
    },
    _handle_check_governance_policy
)

procurement_registry.register(
    {
        "name": "execute_purchase",
        "description": "Execute purchasing transaction for quote.",
        "parameters": {
            "type": "object",
            "properties": {
                "quote_id": {"type": "string", "description": "Quote ID"},
                "amount": {"type": "number", "description": "Total amount in USD"}
            },
            "required": ["quote_id", "amount"]
        }
    },
    _handle_execute_purchase
)
