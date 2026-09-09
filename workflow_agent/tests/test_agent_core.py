from django.test import TransactionTestCase
from workflow_orchestrator.models import Organization, Service, Task, Workflow
from workflow_agent.agent_core.llm import complete, estimate_cost
from workflow_agent.agent_core.registry import ToolRegistry, get_global_registry
from workflow_agent.agent_core.dsl import validate_plan_dsl
from workflow_agent.agent_core.materialize import _materialize_plan_dsl
from workflow_agent.agent_core.security import validate_source, is_ip_allowed, fetch_url_safe
from workflow_agent.agent_core.retrieval import recall_context_items
from workflow_agent.agent_core.lifecycle import start_agent_plan
from workflow_agent.models import AgentRun


class AgentCorePrimitivesTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Agent Core Test Org")
        self.service = Service.objects.create(name="llm_test_service", metadata={"input_price": 1.0, "output_price": 2.0})

    def test_llm_complete_mock_fallback(self):
        # When no API key is provided, complete() falls back to mock response
        res = self.run_async(complete(
            model_resource={"name": "gpt-4o", "metadata": {"provider": "mock"}},
            messages=[{"role": "user", "content": "Hello agent core"}]
        ))
        self.assertEqual(res["stop_reason"], "end_turn")
        self.assertIn("content", res)

    def test_estimate_cost_calculation(self):
        cost = estimate_cost(self.service, prompt_tokens=1_000_000, completion_tokens=1_000_000)
        self.assertEqual(cost, 3.0)

    def test_tool_registry_isolated_instance(self):
        reg = ToolRegistry("test_agent_registry")
        def mock_handler(args, ctx):
            return {"status": "success", "echo": args.get("val")}

        tool_def = {
            "name": "echo_tool",
            "description": "Echoes input value",
            "parameters": {"type": "object", "properties": {"val": {"type": "string"}}}
        }
        reg.register(tool_def, mock_handler)
        self.assertEqual(len(reg.get_definitions()), 1)

        res = reg.dispatch("echo_tool", {"val": "hello_core"})
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["echo"], "hello_core")

    def test_global_registry_populated(self):
        glob_reg = get_global_registry()
        defs = glob_reg.get_definitions()
        self.assertGreaterEqual(len(defs), 10)
        names = [d["name"] for d in defs]
        self.assertIn("list_services", names)

    def test_dsl_validation_and_materialize(self):
        valid_plan = {
            "tasks": [
                {"slug": "core-task-a", "name": "Core Task A", "task_type": "http"},
                {"slug": "core-task-b", "name": "Core Task B", "task_type": "http"}
            ],
            "workflows": [
                {"task_slug": "core-task-a"},
                {"task_slug": "core-task-b"}
            ],
            "workflow_links": [
                {"parent_task_slug": "core-task-a", "child_task_slug": "core-task-b"}
            ],
            "workflow_continuations": [],
            "task_continuations": []
        }
        is_valid, err = validate_plan_dsl(valid_plan)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        summary = _materialize_plan_dsl(valid_plan, self.org)
        self.assertEqual(summary["tasks_created"], 2)
        self.assertEqual(summary["workflows_created"], 2)
        self.assertEqual(summary["links_created"], 1)

        self.assertTrue(Task.objects.filter(slug="core-task-a").exists())
        self.assertTrue(Workflow.objects.filter(organization=self.org, task__slug="core-task-a").exists())

    def test_security_sanitizer_and_ssrf(self):
        # Valid python source
        is_valid_src, err_src = validate_source("def run(data): return data")
        self.assertTrue(is_valid_src)

        # Forbidden import
        is_valid_bad, err_bad = validate_source("import os\nos.system('ls')")
        self.assertFalse(is_valid_bad)
        self.assertIn("Forbidden", err_bad)

        # SSRF checks
        self.assertFalse(is_ip_allowed("127.0.0.1"))
        self.assertTrue(is_ip_allowed("8.8.8.8"))

    def test_retrieval_recall_context(self):
        res = recall_context_items("test")
        self.assertEqual(res["status"], "success")

    import asyncio
    def run_async(self, coro):
        import asyncio
        return asyncio.run(coro)
