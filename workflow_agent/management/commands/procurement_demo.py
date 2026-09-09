"""
Procurement Agent CLI Demo Management Command.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from workflow_agent.agents.procurement.loop import run_procurement_agent
from workflow_orchestrator.conf import get_organization_model


class Command(BaseCommand):
    help = "Run Procurement Agent demo: Supplier discovery -> Quote -> Bounded Purchase"

    def handle(self, *args, **options):
        settings.USE_FAKEREDIS = True

        self.stdout.write(self.style.SUCCESS("\n=========================================================================="))
        self.stdout.write(self.style.SUCCESS("  PROCUREMENT AGENT DEMONSTRATOR"))
        self.stdout.write(self.style.SUCCESS("  Supplier Discovery -> Discount Negotiation -> Bounded Purchase"))
        self.stdout.write(self.style.SUCCESS("==========================================================================\n"))

        Organization = get_organization_model()
        org, _ = Organization.objects.get_or_create(name="Procurement Demo Org")

        result = run_procurement_agent(org.id, item_name="Industrial Sensors", quantity=100)

        self.stdout.write(f"  ✓ Item Requisition: 100x {result['item_name']}")
        self.stdout.write(f"  ✓ Suppliers Found: {result['suppliers_found']}")
        self.stdout.write(f"  ✓ Quote Issued: {result['quote']['quote_id']} (${result['quote']['total_price_usd']:,.2f})")
        self.stdout.write(f"  ✓ Governance Authorized: {result['decision']['authorized']}")
        self.stdout.write(self.style.SUCCESS(f"  ✓ Purchase Confirmed: Tx #{result['purchase']['transaction_id']}"))

        self.stdout.write(self.style.SUCCESS("\n==========================================================================\n"))
