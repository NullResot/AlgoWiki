import time

from django.core.management.base import BaseCommand

from wiki.ai_moderation import process_due_ai_moderation_records


class Command(BaseCommand):
    help = "Process pending AI moderation retries."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--interval", type=int, default=30)

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 500))
        interval = max(1, int(options["interval"]))
        while True:
            processed = process_due_ai_moderation_records(limit=limit)
            if processed:
                self.stdout.write(f"Processed {processed} moderation record(s).")
            if options["once"]:
                return
            time.sleep(interval)
