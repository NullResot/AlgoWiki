from django.db import migrations, models


def populate_draft_identities(apps, schema_editor):
    Submission = apps.get_model("wiki", "SchoolSurveySubmission")
    duplicate_groups = (
        Submission.objects.filter(status="draft", author_id__isnull=False)
        .values("school_id", "author_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
    )
    for group in duplicate_groups.iterator():
        drafts = Submission.objects.filter(
            status="draft",
            school_id=group["school_id"],
            author_id=group["author_id"],
        ).order_by("-updated_at", "-id")
        keep_id = drafts.values_list("id", flat=True).first()
        drafts.exclude(id=keep_id).update(status="archived", draft_identity=None)

    for submission in Submission.objects.filter(
        status="draft",
        author_id__isnull=False,
    ).iterator():
        submission.draft_identity = f"{submission.school_id}:{submission.author_id}"
        submission.save(update_fields=["draft_identity"])


def clear_draft_identities(apps, schema_editor):
    Submission = apps.get_model("wiki", "SchoolSurveySubmission")
    Submission.objects.update(draft_identity=None)


class Migration(migrations.Migration):
    dependencies = [("wiki", "0071_pulse_topic_proposal")]

    operations = [
        migrations.AddField(
            model_name="schoolsurveysubmission",
            name="draft_identity",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=80,
                null=True,
            ),
        ),
        migrations.RunPython(populate_draft_identities, clear_draft_identities),
        migrations.AlterField(
            model_name="schoolsurveysubmission",
            name="draft_identity",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=80,
                null=True,
                unique=True,
            ),
        ),
    ]
