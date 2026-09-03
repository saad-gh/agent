from django.test import TransactionTestCase, override_settings
from workflow_orchestrator.models import Organization, Service, Resource, Task, Workflow
from workflow_agent.models import AgentRun, AgentMessage, JinjaHelper, GeneratedFunction, ManualStep
from workflow_agent.tools import get_tool_definitions, dispatch_tool
from workflow_agent.dsl import validate_plan_dsl, render_plan_dsl
from workflow_agent.planner_topology import ensure_planner_workflow_for_org
from workflow_agent.agent_loop import start_agent_plan, resume_agent_plan


class ToolRegistryAndDSLTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Tool Org")
        self.service = Service.objects.create(name="shopify", metadata={"input_price": 1.0})

    def test_get_tool_definitions(self):
        tools = get_tool_definitions()
        self.assertGreaterEqual(len(tools), 12)
        names = [t["name"] for t in tools]
        self.assertIn("list_services", names)
        self.assertIn("define_jinja_helper", names)
        self.assertIn("define_python_function", names)
        self.assertIn("finalize_plan", names)

    def test_tool_dispatch_list_services(self):
        res = dispatch_tool("list_services", {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(any(s["name"] == "shopify" for s in res["services"]))

    def test_tool_dispatch_define_helpers(self):
        res_j = dispatch_tool("define_jinja_helper", {"name": "test_j_helper", "source": "def test_j_helper(): return 1"})
        self.assertEqual(res_j["status"], "success")
        self.assertFalse(res_j["is_approved"])
        self.assertTrue(JinjaHelper.objects.filter(name="test_j_helper").exists())

        res_p = dispatch_tool("define_python_function", {"slug": "test-p-func", "source": "def run(): return 2"})
        self.assertEqual(res_p["status"], "success")
        self.assertFalse(res_p["is_approved"])
        self.assertTrue(GeneratedFunction.objects.filter(slug="test-p-func").exists())

    def test_tool_dispatch_manual_step(self):
        res = dispatch_tool("declare_manual_step", {"description": "Configure OAuth in Shopify dashboard"})
        self.assertEqual(res["status"], "success")
        self.assertTrue(ManualStep.objects.filter(description="Configure OAuth in Shopify dashboard").exists())

    def test_valid_dsl_validation(self):
        valid_plan = {
            "tasks": [
                {"slug": "task-a", "name": "Task A", "task_type": "http"},
                {"slug": "task-b", "name": "Task B", "task_type": "http"}
            ],
            "workflows": [
                {"task_slug": "task-a"},
                {"task_slug": "task-b"}
            ],
            "workflow_links": [
                {"parent_task_slug": "task-a", "child_task_slug": "task-b"}
            ],
            "workflow_continuations": [],
            "task_continuations": []
        }
        is_valid, err = validate_plan_dsl(valid_plan)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_dsl_cycle_detection(self):
        cyclic_plan = {
            "tasks": [
                {"slug": "task-x", "name": "Task X", "task_type": "http"},
                {"slug": "task-y", "name": "Task Y", "task_type": "http"}
            ],
            "workflows": [
                {"task_slug": "task-x"},
                {"task_slug": "task-y"}
            ],
            "workflow_links": [
                {"parent_task_slug": "task-x", "child_task_slug": "task-y"},
                {"parent_task_slug": "task-y", "child_task_slug": "task-x"}  # Cycle!
            ],
            "workflow_continuations": [],
            "task_continuations": []
        }
        is_valid, err = validate_plan_dsl(cyclic_plan)
        self.assertFalse(is_valid)
        self.assertIn("cycle", err.lower())


class PlannerLoopIntegrationTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Planner Loop Org")

    @override_settings(TASK_EXECUTORS={'llm': 'workflow_agent.executors.LLMExecutor'})
    def test_planner_topology_creation(self):
        wf_plan, wf_tool = ensure_planner_workflow_for_org(self.org)
        self.assertEqual(wf_plan.task.slug, "llm-plan")
        self.assertEqual(wf_tool.task.slug, "execute-tool")
        self.assertIn(wf_plan, wf_tool.mapped_by.all())

    @override_settings(TASK_EXECUTORS={'llm': 'workflow_agent.executors.LLMExecutor'})
    def test_start_agent_plan_execution(self):
        run = start_agent_plan(self.org.id, prompt="Create a workflow to sync shopify orders and xero invoices")
        self.assertIsInstance(run, AgentRun)
        self.assertEqual(run.organization_id, self.org.id)
        self.assertGreater(run.messages.count(), 0)
        first_msg = run.messages.first()
        self.assertEqual(first_msg.role, "user")
        self.assertIn("shopify", first_msg.content)
