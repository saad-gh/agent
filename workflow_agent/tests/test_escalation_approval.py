import json
from django.test import TransactionTestCase, Client
from workflow_orchestrator.models import Organization, Task, Workflow, Checkpoint
from workflow_agent.models import AgentRun, ManualStep


class EscalationApprovalViewTest(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Escalation View Org")
        self.task = Task.objects.create(slug="purchase-task", name="Purchase Task", task_type="http")
        self.workflow = Workflow.objects.create(organization=self.org, task=self.task)

    def test_approve_manual_step_endpoint(self):
        step = ManualStep.objects.create(
            organization=self.org,
            description="APPROVAL REQUIRED: Transaction $12,000 exceeds limit of $5,000",
            status=ManualStep.STATUS_PENDING,
            workflow=self.workflow
        )

        resp = self.client.post(
            f'/agent/step/{step.id}/approve/',
            data=json.dumps({"result_input": {"approved_by": "vp_finance@apex.com"}}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "approved")
        self.assertEqual(data["step_id"], step.id)

        step.refresh_from_db()
        self.assertEqual(step.status, ManualStep.STATUS_DONE)
        self.assertEqual(step.result_input["approved_by"], "vp_finance@apex.com")
