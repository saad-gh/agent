"""
Agent A (Endpoint Specialist) CLI Demo Management Command.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from workflow_agent.agents.endpoint_specialist.loop import run_endpoint_specialist
from workflow_orchestrator.conf import get_organization_model


class Command(BaseCommand):
    help = "Run Agent A (Endpoint Specialist) demo: Raw API Docs -> Standardized Spec -> Service.api_spec_path"

    def handle(self, *args, **options):
        settings.USE_FAKEREDIS = True

        self.stdout.write(self.style.SUCCESS("\n=========================================================================="))
        self.stdout.write(self.style.SUCCESS("  AGENT A (ENDPOINT SPECIALIST) DEMONSTRATOR"))
        self.stdout.write(self.style.SUCCESS("  Transforming raw docs -> Standardized Spec YAML -> Service.api_spec_path"))
        self.stdout.write(self.style.SUCCESS("==========================================================================\n"))

        Organization = get_organization_model()
        org, _ = Organization.objects.get_or_create(name="Agent A Demo Org")

        result = run_endpoint_specialist(org.id, prompt="Ingest shopify API documentation")

        self.stdout.write(f"  ✓ Agent Execution: {result['status']}")
        self.stdout.write(f"  ✓ Service: {result['service']}")
        self.stdout.write(f"  ✓ Standardized Spec Path: {result['api_spec_path']}")
        self.stdout.write(f"  ✓ Endpoints Normalized: {result['endpoints_count']}")
        self.stdout.write(self.style.SUCCESS("\n==========================================================================\n"))
