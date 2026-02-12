from django.core.management.base import BaseCommand

from ticket.services_stockout import StockoutIncidentService


class Command(BaseCommand):
    help = "Detect and synchronize stockout incidents for the current business window."

    def handle(self, *args, **options):
        summary = StockoutIncidentService.detect_and_sync()
        self.stdout.write(
            self.style.SUCCESS(
                "Stockout detection completed: "
                f"action={summary['action']} "
                f"incident_id={summary.get('incident_id')} "
                f"ready_count={summary['ready_count']} "
                f"in_business_window={summary['in_business_window']}"
            )
        )
