from django.test import TransactionTestCase
from workflow_orchestrator.models import Organization
from workflow_agent.tools import dispatch_tool, get_tool_definitions


class ProcurementToolsTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Procurement Tools Org")

    def test_procurement_tools_registered(self):
        tools = get_tool_definitions()
        names = [t["name"] for t in tools]
        self.assertIn("search_suppliers", names)
        self.assertIn("get_quote", names)
        self.assertIn("check_governance_policy", names)

    def test_tool_dispatch_search_suppliers(self):
        res = dispatch_tool("search_suppliers", {"item_name": "Sensors", "quantity": 100})
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["suppliers"]), 3)
        self.assertEqual(res["suppliers"][0]["total_price_usd"], 4500.0)

    def test_tool_dispatch_get_quote(self):
        res = dispatch_tool("get_quote", {
            "supplier_id": "sup-001",
            "item_name": "Sensors",
            "quantity": 100,
            "target_discount_pct": 10.0
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["total_price_usd"], 4050.0)
        self.assertEqual(res["discount_applied_pct"], 10.0)

    def test_tool_dispatch_check_governance_policy(self):
        res = dispatch_tool("check_governance_policy", {"action": "purchase", "amount": 4000.0})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["decision"]["authorized"])

        res_over = dispatch_tool("check_governance_policy", {"action": "purchase", "amount": 10000.0})
        self.assertEqual(res_over["status"], "success")
        self.assertFalse(res_over["decision"]["authorized"])
