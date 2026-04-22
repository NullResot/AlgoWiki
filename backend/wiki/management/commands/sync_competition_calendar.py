from django.core.management.base import BaseCommand, CommandError

from wiki.competition_calendar import normalize_source_sites, sync_competition_calendar


class Command(BaseCommand):
    help = "Fetch competition calendar events from Codeforces, AtCoder, 牛客, 洛谷."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sites",
            default="",
            help="Comma-separated sites: codeforces,atcoder,nowcoder,luogu",
        )
        parser.add_argument(
            "--past-days",
            type=int,
            default=180,
            help="Keep ended contests whose end_time is within this many past days.",
        )
        parser.add_argument(
            "--future-days",
            type=int,
            default=365,
            help="Keep upcoming contests whose start_time is within this many future days.",
        )

    def handle(self, *args, **options):
        requested_sites = [
            item.strip()
            for item in str(options.get("sites", "") or "").split(",")
            if item.strip()
        ]
        sites = normalize_source_sites(requested_sites)
        summary = sync_competition_calendar(
            source_sites=sites,
            past_days=int(options.get("past_days") or 180),
            future_days=int(options.get("future_days") or 365),
        )

        for site in sites:
            site_summary = summary["sites"].get(site, {})
            if site_summary.get("error"):
                self.stdout.write(
                    self.style.WARNING(
                        f"[{site}] failed: {site_summary['error']}"
                    )
                )
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{site}] fetched={site_summary.get('fetched', 0)} "
                    f"created={site_summary.get('created', 0)} "
                    f"updated={site_summary.get('updated', 0)} "
                    f"deleted={site_summary.get('deleted', 0)} "
                    f"skipped={site_summary.get('skipped', 0)}"
                )
            )

        self.stdout.write(
            f"summary: created={summary['created']} updated={summary['updated']} "
            f"deleted={summary.get('deleted', 0)} skipped={summary['skipped']}"
        )

        if summary["failed_sites"] and len(summary["failed_sites"]) == len(sites):
            raise CommandError("Competition calendar sync failed for all requested sites.")
