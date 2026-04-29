from django.db import migrations


def ensure_competition_practice_section(apps, schema_editor):
    CompetitionZoneSection = apps.get_model("wiki", "CompetitionZoneSection")

    CompetitionZoneSection.objects.update_or_create(
        key="practice",
        defaults={
            "title": "补题链接",
            "target_type": "builtin",
            "builtin_view": "practice",
            "display_order": 5,
            "is_visible": True,
            "page": None,
        },
    )

    CompetitionZoneSection.objects.filter(key="qa", display_order__lte=5).update(
        display_order=6
    )


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0045_trickentry_delete_vote_review_note_and_more"),
    ]

    operations = [
        migrations.RunPython(
            ensure_competition_practice_section,
            migrations.RunPython.noop,
        ),
    ]
