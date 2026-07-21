from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from wiki.pulse.services import get_or_create_daily_edition


class Command(BaseCommand):
    help = "Pre-create one Midnight Pulse daily edition."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="Shanghai business date in YYYY-MM-DD format. Defaults to today.",
        )

    def handle(self, *args, **options):
        target = None
        if options.get("date"):
            try:
                target = datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("--date must use YYYY-MM-DD") from exc
        edition = get_or_create_daily_edition(business_date=target)
        self.stdout.write(
            self.style.SUCCESS(
                f"Midnight Pulse {edition.date.isoformat()} ready (edition {edition.id})."
            )
        )
