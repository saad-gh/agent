from django.test import TransactionTestCase
from workflow_orchestrator.models import Organization
from workflow_agent.models import ManualStep
from workflow_agent.agents.governance.tools import governance_registry, _handle_check_policy, _handle_approve_step
from workflow_agent.agents.governance.loop import run_governance_agent
from workflow_agent.agents.procurement.tools import procurement_registry, _handle_execute_purchase
from workflow_agent.agents.procurement.loop import run_procurement_agent


class Phase4AgentsTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Phase 4 Test Org")

    def test_governance_agent_registry_and_tools(self):
        defs = governance_registry.get_definitions()
        self.assertEqual(len(defs), 2)
        names = [d["name"] for d in defs]
        self.assertIn("check_governance_policy", names)
        self.assertIn("approve_escalated_step", names)

        # Check policy
        res_check = _handle_check_policy({"organization_id": self.org.id, "action": "purchase", "amount": 4000.0})
        self.assertEqual(res_check["status"], "success")
        self.assertTrue(res_check["decision"]["authorized"])

        # Create step and approve
        step = ManualStep.objects.create(organization=self.org, description="Test step", status=ManualStep.STATUS_PENDING)
        res_approve = _handle_approve_step({"step_id": step.id, "approved_by": "admin@apex.com"})
        self.assertEqual(res_approve["status"], "success")
        step.refresh_from_db()
        self.assertEqual(step.status, ManualStep.STATUS_DONE)

    def test_governance_agent_loop_execution(self):
        res_ok = run_governance_agent(self.org.id, action="purchase", amount=3500.00)
        self.assertEqual(res_ok["status"], "completed")
        self.assertTrue(res_ok["authorized"])

        res_escalated = run_governance_agent(self.org.id, action="purchase", amount=15000.00)
        self.assertEqual(res_escalated["status"], "escalated_pending_approval")
        self.assertFalse(res_escalated["authorized"])
        self.assertIsNotNone(res_escalated["manual_step_id"])

    def test_procurement_agent_registry_and_tools(self):
        defs = procurement_registry.get_definitions()
        self.assertEqual(len(defs), 4)
        names = [d["name"] for d in defs]
        self.assertIn("search_suppliers", names)
        self.assertIn("get_quote", names)
        self.assertIn("check_governance_policy", names)
        self.assertIn("execute_purchase", names)

        res_tx = _handle_execute_purchase({"organization_id": self.org.id, "quote_id": "QT-SUP-001-8821", "amount": 4050.00})
        self.assertEqual(res_tx["status"], "success")
        self.assertIn("TX-PROC", res_tx["transaction_id"])

    def test_procurement_agent_loop_execution(self):
        res = run_procurement_agent(self.org.id, item_name="Sensors", quantity=100)
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["suppliers_found"], 3)
        self.assertTrue(res["decision"]["authorized"])
        self.assertEqual(res["purchase"]["status"], "success")
