"""
Governance Agent CLI Demo Management Command.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from workflow_agent.agents.governance.loop import run_governance_agent
from workflow_orchestrator.conf import get_organization_model


class Command(BaseCommand):
    help = "Run Governance Agent demo: Delegated spending limit check & escalation"

    def handle(self, *args, **options):
        settings.USE_FAKEREDIS = True

        self.stdout.write(self.style.SUCCESS("\n=========================================================================="))
        self.stdout.write(self.style.SUCCESS("  GOVERNANCE AGENT DEMONSTRATOR"))
        self.stdout.write(self.style.SUCCESS("  Bounded Authority Policy Check & Human Escalation Boundary"))
        self.stdout.write(self.style.SUCCESS("==========================================================================\n"))

        Organization = get_organization_model()
        org, _ = Organization.objects.get_or_create(
            name="Governance Demo Org",
            defaults={"metadata": {"governance_policy": {"delegated_spending_limit": 5000.00}}}
        )

        # Scenario A: Authorized ($4,050 <= $5,000)
        res_a = run_governance_agent(org.id, action="purchase", amount=4050.00)
        self.stdout.write(self.style.SUCCESS(f"  [Scenario A: $4,050.00] Authorized={res_a['authorized']} | {res_a['decision']['reason']}"))

        # Scenario B: Escalated ($12,000 > $5,000)
        res_b = run_governance_agent(org.id, action="purchase", amount=12000.00)
        self.stdout.write(self.style.WARNING(f"  [Scenario B: $12,000.00] Authorized={res_b['authorized']} | {res_b['decision']['reason']}"))
        self.stdout.write(self.style.WARNING(f"  ➜ ESCALATED TO HUMAN PRINCIPAL: Created ManualStep #{res_b['manual_step_id']}"))

        self.stdout.write(self.style.SUCCESS("\n==========================================================================\n"))
