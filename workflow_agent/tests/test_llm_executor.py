import asyncio
from django.test import TransactionTestCase, override_settings
from workflow_orchestrator.models import Organization, Service, Resource, Task, Workflow
from workflow_orchestrator.execution_context import ExecutionContext
from workflow_orchestrator.executors import get_executor
from workflow_agent.cost import estimate_cost
from workflow_agent.llm_client import complete
from workflow_agent.executors import LLMExecutor


class LLMExecutorTest(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Agent Org")
        self.service = Service.objects.create(
            name="OpenAI Service",
            metadata={"input_price": 3.0, "output_price": 15.0}
        )
        self.resource = Resource.objects.create(
            name="gpt-4o",
            service=self.service,
            metadata={"provider": "mock", "model_id": "gpt-4o"}
        )

    def test_cost_estimation(self):
        cost = estimate_cost(self.resource, prompt_tokens=1_000_000, completion_tokens=1_000_000)
        self.assertEqual(cost, 18.0)

    def test_mock_llm_completion(self):
        result = asyncio.run(complete(
            model_resource=self.resource,
            messages=[{"role": "user", "content": "Hello world"}]
        ))
        self.assertIn("content", result)
        self.assertEqual(result["stop_reason"], "end_turn")
        self.assertGreater(result["prompt_tokens"], 0)

    @override_settings(TASK_EXECUTORS={'llm': 'workflow_agent.executors.LLMExecutor'})
    def test_executor_factory_resolves_llm_executor(self):
        executor = get_executor('llm')
        self.assertIsInstance(executor, LLMExecutor)

    def test_llm_executor_execution(self):
        task = Task.objects.create(
            name="LLM Plan Task",
            slug="llm-plan-task",
            task_type="llm",
            resource=self.resource
        )
        workflow = Workflow.objects.create(
            organization=self.org,
            task=task
        )

        from workflow_orchestrator.graph import TaskNode
        node = TaskNode(workflow)

        context = ExecutionContext(run_id="run-101", org_id=self.org.id)
        context.update_task_params("llm-plan-task", {
            "messages": [{"role": "user", "content": "Plan a workflow to sync sales"}]
        })

        executor = LLMExecutor()
        result = asyncio.run(executor.execute(context, node))

        self.assertEqual(result["status"], "success")
        self.assertIn("content", result)
        self.assertIn("cost", result)
        self.assertIn("total_tokens", result)
