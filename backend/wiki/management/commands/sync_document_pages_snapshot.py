from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from wiki.models import DocumentPageSection
from wiki.seed_content.document_pages import (
    SNAPSHOT_PATH,
    dump_document_page_defs,
    load_document_page_defs,
    sync_document_page_defs_to_database,
)


class Command(BaseCommand):
    help = "Sync document-page content between the database and the repository snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--direction",
            choices=["export", "import"],
            default="export",
            help="export writes database content to the snapshot; import restores from it.",
        )
        parser.add_argument(
            "--path",
            default=str(SNAPSHOT_PATH),
            help="Snapshot JSON path. Defaults to the repository snapshot file.",
        )
        parser.add_argument(
            "--overwrite-content",
            action="store_true",
            help="When importing, replace non-empty database content with snapshot content.",
        )
        parser.add_argument(
            "--overwrite-metadata",
            action="store_true",
            help="When importing, replace titles, visibility and ordering from the snapshot.",
        )

    def handle(self, *args, **options):
        direction = options["direction"]
        path = options["path"]

        if direction == "export":
            rows = []
            for section in DocumentPageSection.objects.select_related("page").order_by(
                "display_order", "id"
            ):
                page = section.page
                if not page:
                    continue
                rows.append(
                    {
                        "key": section.key,
                        "slug": page.slug,
                        "section_title": section.title,
                        "page_title": page.title,
                        "description": page.description,
                        "content_md": page.content_md,
                        "display_order": section.display_order,
                        "access_level": page.access_level,
                        "is_enabled": page.is_enabled,
                        "is_visible": section.is_visible,
                    }
                )
            target_path = dump_document_page_defs(rows, path)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Exported {len(rows)} document pages to {target_path}"
                )
            )
            return

        with transaction.atomic():
            stats = sync_document_page_defs_to_database(
                load_document_page_defs(path),
                overwrite_content=options["overwrite_content"],
                overwrite_metadata=options["overwrite_metadata"],
            )
        self.stdout.write(self.style.SUCCESS(f"Imported document pages: {stats}"))
