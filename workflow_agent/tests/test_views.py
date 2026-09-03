import json
from django.test import TransactionTestCase, Client, override_settings
from workflow_orchestrator.models import Organization, Task, Workflow
from workflow_agent.models import AgentRun, AgentMessage
from workflow_agent.search import is_ip_allowed, fetch_url_safe, search_api_docs
from workflow_agent.retrieval import recall_context_items


class SearchAndSSRFTest(TransactionTestCase):
    def test_ssrf_guard_ip_filtering(self):
        # 1. Loopback & Private IPs must be rejected
        self.assertFalse(is_ip_allowed('127.0.0.1'))
        self.assertFalse(is_ip_allowed('10.0.0.1'))
        self.assertFalse(is_ip_allowed('172.16.0.1'))
        self.assertFalse(is_ip_allowed('192.168.1.1'))
        self.assertFalse(is_ip_allowed('169.254.169.254'))

        # 2. Public IPs allowed
        self.assertTrue(is_ip_allowed('8.8.8.8'))
        self.assertTrue(is_ip_allowed('1.1.1.1'))

    def test_fetch_url_safe_blocks_ssrf(self):
        res_loopback = fetch_url_safe('http://127.0.0.1/secret')
        self.assertEqual(res_loopback['status'], 'error')
        self.assertIn('SSRF Protection', res_loopback['error'])

        res_meta = fetch_url_safe('http://169.254.169.254/latest/meta-data')
        self.assertEqual(res_meta['status'], 'error')
        self.assertIn('SSRF Protection', res_meta['error'])

    def test_search_provider_escalation(self):
        res = search_api_docs("shopify orders API")
        self.assertEqual(res['status'], 'success')
        self.assertIn('provider', res)
        self.assertGreaterEqual(len(res['results']), 1)

    def test_retrieval_recall(self):
        res = recall_context_items("shopify")
        self.assertEqual(res['status'], 'success')
        self.assertIn('recalled', res)


class AgentViewsAndApprovalTest(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="View Test Org")

    @override_settings(TASK_EXECUTORS={'llm': 'workflow_agent.executors.LLMExecutor'})
    def test_start_and_get_agent_run_view(self):
        # 1. Start Agent Run
        resp = self.client.post(
            '/agent/run/',
            data=json.dumps({"organization_id": self.org.id, "prompt": "Sync shopify orders and xero invoices"}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        run_id = data["agent_run_id"]
        self.assertIsNotNone(run_id)

        # 2. Get Agent Run status and transcript
        get_resp = self.client.get(f'/agent/run/{run_id}/')
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()
        self.assertEqual(get_data["agent_run_id"], run_id)
        self.assertGreater(len(get_data["messages"]), 0)

        # 3. Answer Agent Run question
        ans_resp = self.client.post(
            f'/agent/run/{run_id}/message/',
            data=json.dumps({"user_input": "Use shopify store my-store.myshopify.com"}),
            content_type='application/json'
        )
        self.assertEqual(ans_resp.status_code, 200)

    @override_settings(TASK_EXECUTORS={'llm': 'workflow_agent.executors.LLMExecutor'})
    def test_approve_agent_plan_materializes_workflows(self):
        # Create an AgentRun with a valid proposed plan
        valid_plan = {
            "tasks": [
                {"slug": "shopify-get-orders", "name": "Shopify Get Orders", "task_type": "http"},
                {"slug": "xero-create-invoices", "name": "Xero Create Invoices", "task_type": "http"}
            ],
            "workflows": [
                {"task_slug": "shopify-get-orders"},
                {"task_slug": "xero-create-invoices"}
            ],
            "workflow_links": [
                {"parent_task_slug": "shopify-get-orders", "child_task_slug": "xero-create-invoices"}
            ],
            "workflow_continuations": [],
            "task_continuations": []
        }

        run = AgentRun.objects.create(
            organization=self.org,
            prompt="Build shopify to xero sync",
            plan_json=valid_plan,
            status=AgentRun.STATUS_PLANNING
        )

        # POST approve endpoint
        resp = self.client.post(f'/agent/run/{run.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "approved")

        # Verify Tasks and Workflows materialized in database
        self.assertTrue(Task.objects.filter(slug="shopify-get-orders").exists())
        self.assertTrue(Task.objects.filter(slug="xero-create-invoices").exists())

        wf_shopify = Workflow.objects.filter(organization=self.org, task__slug="shopify-get-orders").first()
        wf_xero = Workflow.objects.filter(organization=self.org, task__slug="xero-create-invoices").first()

        self.assertIsNotNone(wf_shopify)
        self.assertIsNotNone(wf_xero)
        self.assertIn(wf_shopify, wf_xero.mapped_by.all())
