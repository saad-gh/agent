from django.test import TransactionTestCase
from workflow_orchestrator.models import Organization, Service, Task, Workflow
from workflow_agent.agents.endpoint_specialist.tools import endpoint_registry, _handle_normalize_spec, _handle_upsert_api_spec
from workflow_agent.agents.endpoint_specialist.loop import run_endpoint_specialist
from workflow_agent.agents.workflow_architect.tools import architect_registry, _handle_load_service_spec, _handle_submit_workflow_plan
from workflow_agent.agents.workflow_architect.loop import run_workflow_architect


class Phase3AgentsTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Phase 3 Test Org")
        self.service = Service.objects.create(name="shopify")

    def test_agent_a_endpoint_specialist_tools(self):
        defs = endpoint_registry.get_definitions()
        self.assertEqual(len(defs), 3)
        names = [d["name"] for d in defs]
        self.assertIn("read_raw_doc", names)
        self.assertIn("normalize_spec", names)
        self.assertIn("upsert_api_spec", names)

        # Normalize spec
        norm_res = _handle_normalize_spec({
            "service_name": "shopify",
            "version": "2024-01",
            "endpoints": [
                {"slug": "shopify_orders", "method": "GET", "path": "/admin/api/2024-01/orders.json"}
            ]
        })
        self.assertEqual(norm_res["status"], "success")

        # Upsert spec
        upsert_res = _handle_upsert_api_spec({
            "service_name": "shopify",
            "spec_data": norm_res["spec_data"]
        })
        self.assertEqual(upsert_res["status"], "success")

        self.service.refresh_from_db()
        self.assertTrue(self.service.api_spec_path.endswith(".yaml"))

    def test_agent_b_workflow_architect_tools(self):
        defs = architect_registry.get_definitions()
        self.assertEqual(len(defs), 3)
        names = [d["name"] for d in defs]
        self.assertIn("list_service_specs", names)
        self.assertIn("load_service_spec", names)
        self.assertIn("submit_workflow_plan", names)

    def test_inter_agent_contract_flow(self):
        # Step 1: Agent A transforms raw docs -> standardized spec -> Service.api_spec_path
        res_a = run_endpoint_specialist(self.org.id, prompt="Process shopify docs")
        self.assertEqual(res_a["status"], "completed")
        self.assertIsNotNone(res_a["api_spec_path"])

        # Step 2: Agent B reads Service.api_spec_path -> 5-array plan -> Materializes DB rows
        res_b = run_workflow_architect(self.org.id, service_name="shopify")
        self.assertEqual(res_b["status"], "completed")
        self.assertIsNotNone(res_b["materialized"])
        self.assertEqual(res_b["materialized"]["tasks_created"], 2)

        # Verify materialized Task & Workflow DB rows
        self.assertTrue(Task.objects.filter(slug="shopify_list_orders").exists())
        self.assertTrue(Workflow.objects.filter(organization=self.org, task__slug="shopify_list_orders").exists())
