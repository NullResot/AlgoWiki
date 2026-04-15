from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


SNAPSHOT_PATH = Path(__file__).with_name("document_pages_snapshot.json")


def _as_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def normalize_document_page_defs(rows: Iterable[dict]) -> list[dict]:
    normalized = []
    for index, row in enumerate(rows):
        key = str(row.get("key") or "").strip()
        slug = str(row.get("slug") or row.get("page_slug") or key).strip()
        if not key or not slug:
            continue
        normalized.append(
            {
                "key": key,
                "slug": slug,
                "section_title": str(
                    row.get("section_title") or row.get("title") or key
                ).strip(),
                "page_title": str(
                    row.get("page_title") or row.get("title") or key
                ).strip(),
                "description": str(row.get("description") or "").strip(),
                "content_md": str(row.get("content_md") or ""),
                "display_order": int(row.get("display_order") or (index + 1) * 10),
                "access_level": str(row.get("access_level") or "public").strip()
                or "public",
                "is_enabled": _as_bool(row.get("is_enabled"), True),
                "is_visible": _as_bool(row.get("is_visible"), True),
            }
        )
    return normalized


def load_document_page_defs(path: str | Path | None = None) -> list[dict]:
    source_path = Path(path) if path else SNAPSHOT_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    rows = payload.get("pages", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Document page snapshot must contain a list of pages.")
    return normalize_document_page_defs(rows)


def dump_document_page_defs(rows: Iterable[dict], path: str | Path | None = None) -> Path:
    target_path = Path(path) if path else SNAPSHOT_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pages": normalize_document_page_defs(rows)}
    target_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target_path


def sync_document_page_defs_to_database(
    rows: Iterable[dict],
    *,
    overwrite_content: bool = False,
    overwrite_metadata: bool = False,
) -> dict[str, int]:
    from wiki.models import DocumentPageSection, ExtensionPage

    stats = {
        "pages_created": 0,
        "pages_updated": 0,
        "sections_created": 0,
        "sections_updated": 0,
    }

    for item in normalize_document_page_defs(rows):
        page, page_created = ExtensionPage.objects.get_or_create(
            slug=item["slug"],
            defaults={
                "title": item["page_title"],
                "description": item["description"],
                "content_md": item["content_md"],
                "access_level": item["access_level"],
                "is_enabled": item["is_enabled"],
            },
        )
        if page_created:
            stats["pages_created"] += 1
        else:
            update_fields = []
            if overwrite_metadata or not str(page.title or "").strip():
                page.title = item["page_title"]
                update_fields.append("title")
            if overwrite_metadata or not str(page.description or "").strip():
                page.description = item["description"]
                update_fields.append("description")
            if overwrite_content or not str(page.content_md or "").strip():
                page.content_md = item["content_md"]
                update_fields.append("content_md")
            if overwrite_metadata and page.access_level != item["access_level"]:
                page.access_level = item["access_level"]
                update_fields.append("access_level")
            if overwrite_metadata and page.is_enabled != item["is_enabled"]:
                page.is_enabled = item["is_enabled"]
                update_fields.append("is_enabled")
            if update_fields:
                page.save(update_fields=update_fields + ["updated_at"])
                stats["pages_updated"] += 1

        section, section_created = DocumentPageSection.objects.get_or_create(
            key=item["key"],
            defaults={
                "title": item["section_title"],
                "page": page,
                "display_order": item["display_order"],
                "is_visible": item["is_visible"],
            },
        )
        if section_created:
            stats["sections_created"] += 1
        else:
            update_fields = []
            if overwrite_metadata or not str(section.title or "").strip():
                section.title = item["section_title"]
                update_fields.append("title")
            if overwrite_metadata or not section.page_id:
                section.page = page
                update_fields.append("page")
            if overwrite_metadata and section.display_order != item["display_order"]:
                section.display_order = item["display_order"]
                update_fields.append("display_order")
            if overwrite_metadata and section.is_visible != item["is_visible"]:
                section.is_visible = item["is_visible"]
                update_fields.append("is_visible")
            if update_fields:
                section.save(update_fields=update_fields + ["updated_at"])
                stats["sections_updated"] += 1

    return stats
