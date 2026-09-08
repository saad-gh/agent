from django.test import TransactionTestCase
from workflow_orchestrator.models import Organization
from workflow_agent.governance import evaluate_action_policy, guard_transaction_callable, DEFAULT_DELEGATED_SPENDING_LIMIT
from workflow_agent.models import ManualStep, AgentRun


class GovernancePolicyTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Governance Test Org",
            metadata={
                "governance_policy": {
                    "delegated_spending_limit": 5000.00,
                    "max_discount_percent": 15.0,
                    "allowed_actions": ["search_suppliers", "get_quote", "purchase", "negotiate"]
                }
            }
        )

    def test_evaluate_action_within_limit(self):
        decision = evaluate_action_policy(self.org.id, "purchase", 4500.00)
        self.assertTrue(decision.authorized)
        self.assertFalse(decision.requires_approval)
        self.assertEqual(decision.amount, 4500.00)

    def test_evaluate_action_exceeds_limit(self):
        decision = evaluate_action_policy(self.org.id, "purchase", 12000.00)
        self.assertFalse(decision.authorized)
        self.assertTrue(decision.requires_approval)
        self.assertIn("exceeds delegated authority limit", decision.reason)

    def test_evaluate_negotiation_discount_cap(self):
        # 10% allowed (<= 15%)
        decision_ok = evaluate_action_policy(self.org.id, "negotiate", 1000.00, {"discount_percent": 10.0})
        self.assertTrue(decision_ok.authorized)

        # 25% forbidden (> 15%)
        decision_high = evaluate_action_policy(self.org.id, "negotiate", 1000.00, {"discount_percent": 25.0})
        self.assertFalse(decision_high.authorized)
        self.assertIn("exceeds maximum allowed discount", decision_high.reason)

    def test_guard_transaction_gatekeeper_authorized(self):
        ctx = {
            "kwargs": {"organization_id": self.org.id, "action": "purchase", "amount": 3000.00}
        }
        res = guard_transaction_callable(ctx)
        self.assertEqual(res["status"], "authorized")
        self.assertTrue(res["decision"]["authorized"])

    def test_guard_transaction_gatekeeper_escalates_over_limit(self):
        ctx = {
            "kwargs": {"organization_id": self.org.id, "action": "purchase", "amount": 15000.00}
        }
        res = guard_transaction_callable(ctx)
        self.assertEqual(res["_workflow_action"], "skip")
        self.assertEqual(res["status"], "escalated_for_approval")
        self.assertIn("manual_step_id", res)

        step = ManualStep.objects.get(id=res["manual_step_id"])
        self.assertEqual(step.status, ManualStep.STATUS_PENDING)
        self.assertIn("APPROVAL REQUIRED", step.description)
