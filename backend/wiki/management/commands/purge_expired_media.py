from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from wiki.models import GalleryImage, MomentImage


def delete_media_name(name: str) -> bool:
    relative = str(name or "").replace("\\", "/").strip("/")
    if not relative:
        return False
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return False
    if target.is_file():
        target.unlink()
        return True
    return False


class Command(BaseCommand):
    help = "Purge expired uploaded media files and database rows."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report what would be deleted.")
        parser.add_argument("--limit", type=int, default=500, help="Maximum rows to purge per model.")
        parser.add_argument(
            "--skip-gallery",
            action="store_true",
            help="Only purge expired Moment images, not recycled gallery images.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        limit = max(1, int(options["limit"] or 500))
        dry_run = bool(options["dry_run"])
        moment_rows = list(
            MomentImage.objects.filter(
                delete_after__isnull=False,
                delete_after__lte=now,
            ).order_by("delete_after", "id")[:limit]
        )
        moment_files = 0
        for image in moment_rows:
            if not dry_run:
                moment_files += int(delete_media_name(image.image.name))
                moment_files += int(delete_media_name(image.thumbnail.name))
                image.delete()

        gallery_rows = []
        gallery_files = 0
        if not options["skip_gallery"]:
            gallery_rows = list(
                GalleryImage.objects.filter(
                    status=GalleryImage.Status.RECYCLED,
                    delete_after__isnull=False,
                    delete_after__lte=now,
                ).order_by("delete_after", "id")[:limit]
            )
            for image in gallery_rows:
                if not dry_run:
                    gallery_files += int(delete_media_name(image.image.name))
                    image.delete()

        self.stdout.write(
            self.style.SUCCESS(
                "dry_run={dry_run} moment_rows={moment_rows} moment_files={moment_files} "
                "gallery_rows={gallery_rows} gallery_files={gallery_files}".format(
                    dry_run=int(dry_run),
                    moment_rows=len(moment_rows),
                    moment_files=moment_files,
                    gallery_rows=len(gallery_rows),
                    gallery_files=gallery_files,
                )
            )
        )
