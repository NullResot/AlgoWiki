from django.db import migrations, models


def deduplicate_reports(apps, schema_editor):
    Report = apps.get_model("wiki", "MomentReport")
    groups = (
        Report.objects.values(
            "reporter_id",
            "target_type",
            "moment_id",
            "comment_id",
        )
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
    )
    for group in groups.iterator():
        reports = Report.objects.filter(
            reporter_id=group["reporter_id"],
            target_type=group["target_type"],
            moment_id=group["moment_id"],
            comment_id=group["comment_id"],
        ).order_by("-updated_at", "-id")
        keep_id = reports.values_list("id", flat=True).first()
        reports.exclude(id=keep_id).delete()

    for report in Report.objects.all().iterator():
        target_id = (
            report.comment_id
            if report.target_type == "comment"
            else report.moment_id
        )
        report.report_identity = (
            f"{report.reporter_id}:{report.target_type}:{target_id}"
            if report.reporter_id and target_id
            else None
        )
        report.save(update_fields=["report_identity"])


class Migration(migrations.Migration):
    dependencies = [("wiki", "0073_assistant_atomic_daily_budget")]

    operations = [
        migrations.AddField(
            model_name="momentreport",
            name="report_identity",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=120,
                null=True,
            ),
        ),
        migrations.RunPython(deduplicate_reports, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="momentreport",
            name="report_identity",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=120,
                null=True,
                unique=True,
            ),
        ),
    ]
