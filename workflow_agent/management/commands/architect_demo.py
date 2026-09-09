"""
Agent B (Workflow Architect) CLI Demo Management Command.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from workflow_agent.agents.endpoint_specialist.loop import run_endpoint_specialist
from workflow_agent.agents.workflow_architect.loop import run_workflow_architect
from workflow_orchestrator.conf import get_organization_model


class Command(BaseCommand):
    help = "Run Agent B (Workflow Architect) demo: Service.api_spec_path -> 5-Array Plan DSL -> Materialization"

    def handle(self, *args, **options):
        settings.USE_FAKEREDIS = True

        self.stdout.write(self.style.SUCCESS("\n=========================================================================="))
        self.stdout.write(self.style.SUCCESS("  AGENT B (WORKFLOW ARCHITECT) DEMONSTRATOR"))
        self.stdout.write(self.style.SUCCESS("  Reading Service.api_spec_path -> 5-Array Plan DSL -> Materializing DB Rows"))
        self.stdout.write(self.style.SUCCESS("==========================================================================\n"))

        Organization = get_organization_model()
        org, _ = Organization.objects.get_or_create(name="Agent B Demo Org")

        # 1. Ensure Agent A spec exists first
        run_endpoint_specialist(org.id, prompt="Ingest shopify API documentation")

        # 2. Run Agent B
        result = run_workflow_architect(org.id, service_name="shopify")

        self.stdout.write(f"  ✓ Agent Execution: {result['status']}")
        self.stdout.write(f"  ✓ Service: {result['service']}")
        self.stdout.write(f"  ✓ Read Spec From: {result['api_spec_path']}")
        self.stdout.write(f"  ✓ Materialization Summary: {result['materialized']}")
        self.stdout.write(self.style.SUCCESS("\n==========================================================================\n"))
