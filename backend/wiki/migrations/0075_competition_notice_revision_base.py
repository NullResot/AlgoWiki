from django.db import migrations, models


def populate_safe_revision_bases(apps, schema_editor):
    Notice = apps.get_model("wiki", "CompetitionNotice")
    revisions = Notice.objects.filter(
        revision_of_id__isnull=False,
        status="pending",
    ).select_related("revision_of")
    for revision in revisions.iterator():
        target = revision.revision_of
        if target and target.updated_at <= revision.created_at:
            revision.base_updated_at = target.updated_at
            revision.save(update_fields=["base_updated_at"])


class Migration(migrations.Migration):
    dependencies = [("wiki", "0074_deduplicate_moment_reports")]

    operations = [
        migrations.AddField(
            model_name="competitionnotice",
            name="base_updated_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(
            populate_safe_revision_bases,
            migrations.RunPython.noop,
        ),
    ]
