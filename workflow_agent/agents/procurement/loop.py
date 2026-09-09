"""
Procurement Agent Loop Controller.
"""
import logging
from typing import Dict, Any

from .tools import _handle_search_suppliers, _handle_get_quote, _handle_execute_purchase
from workflow_agent.agents.governance.policy import evaluate_action_policy

logger = logging.getLogger(__name__)


def run_procurement_agent(
    organization_id: int,
    item_name: str = "Industrial Sensors",
    quantity: int = 100,
    target_discount_pct: float = 10.0
) -> Dict[str, Any]:
    """
    Execute Procurement Agent purchasing turn.
    """
    logger.info(f"Running Procurement Agent for Org #{organization_id}: item='{item_name}', qty={quantity}")

    # 1. Search suppliers
    search_res = _handle_search_suppliers({"item_name": item_name, "quantity": quantity}, None)

    # 2. Get Quote
    quote_res = _handle_get_quote({
        "supplier_id": "sup-001",
        "item_name": item_name,
        "quantity": quantity,
        "target_discount_pct": target_discount_pct
    }, None)

    # 3. Check Governance Policy & Execute Purchase
    total_amount = quote_res["total_price_usd"]
    decision = evaluate_action_policy(organization_id, "purchase", total_amount)

    purchase_res = _handle_execute_purchase({
        "organization_id": organization_id,
        "quote_id": quote_res["quote_id"],
        "amount": total_amount
    }, None)

    return {
        "agent": "procurement",
        "organization_id": organization_id,
        "item_name": item_name,
        "quantity": quantity,
        "suppliers_found": len(search_res["suppliers"]),
        "quote": quote_res,
        "decision": decision.to_dict(),
        "purchase": purchase_res,
        "status": "completed" if decision.authorized else "escalated"
    }
