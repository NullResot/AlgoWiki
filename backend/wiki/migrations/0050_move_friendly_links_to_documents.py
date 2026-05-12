from django.db import migrations


def move_friendly_links_to_documents(apps, schema_editor):
    ExtensionPage = apps.get_model("wiki", "ExtensionPage")
    DocumentPageSection = apps.get_model("wiki", "DocumentPageSection")
    HeaderNavigationItem = apps.get_model("wiki", "HeaderNavigationItem")

    page, page_created = ExtensionPage.objects.get_or_create(
        slug="friendly-links",
        defaults={
            "title": "友链",
            "description": "AlgoWiki 相关站点与常用外部资源。",
            "content_md": "",
            "access_level": "public",
            "is_enabled": True,
        },
    )
    if not page.is_enabled:
        page.is_enabled = True
        page.save(update_fields=["is_enabled", "updated_at"])

    section, section_created = DocumentPageSection.objects.get_or_create(
        key="friendly-links",
        defaults={
            "title": "友链",
            "page": page,
            "display_order": 50,
            "is_visible": True,
        },
    )
    if not section_created and section.page_id is None:
        section.page = page
        section.save(update_fields=["page", "updated_at"])

    HeaderNavigationItem.objects.filter(key="friendly-links").update(is_visible=False)


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0049_aimoderationconfig_aimoderationrecord"),
    ]

    operations = [
        migrations.RunPython(move_friendly_links_to_documents, migrations.RunPython.noop),
    ]
