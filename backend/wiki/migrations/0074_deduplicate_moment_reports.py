from django.db import migrations, models
from django.utils import timezone


AUTO_HIDE_REASON = "举报达到阈值，系统已自动隐藏并等待人工复核。"


def repair_report_derivatives(apps, *, moment_ids, comment_ids):
    Report = apps.get_model("wiki", "MomentReport")
    Moment = apps.get_model("wiki", "Moment")
    Comment = apps.get_model("wiki", "MomentComment")
    Settings = apps.get_model("wiki", "MomentSettings")

    settings_obj = Settings.objects.order_by("id").first()
    threshold = max(
        1,
        int(getattr(settings_obj, "auto_hide_report_threshold", 3) or 3),
    )
    like_weight = int(getattr(settings_obj, "hot_like_weight", 2) or 0)
    favorite_weight = int(getattr(settings_obj, "hot_favorite_weight", 3) or 0)
    comment_weight = int(getattr(settings_obj, "hot_comment_weight", 2) or 0)
    report_penalty = int(getattr(settings_obj, "hot_report_penalty", 10) or 0)

    for moment in Moment.objects.filter(pk__in=moment_ids).iterator():
        pending_count = Report.objects.filter(
            moment_id=moment.pk,
            status="pending",
        ).count()
        updates = {
            "report_count": pending_count,
            "hot_score": (
                int(moment.like_count or 0) * like_weight
                + int(moment.favorite_count or 0) * favorite_weight
                + int(moment.comment_count or 0) * comment_weight
                - pending_count * report_penalty
            ),
        }
        if pending_count >= threshold and moment.status == "published":
            updates.update(
                status="hidden",
                hidden_reason=AUTO_HIDE_REASON,
                hidden_at=timezone.now(),
                hidden_by_id=None,
            )
        elif (
            pending_count < threshold
            and moment.status == "hidden"
            and moment.hidden_reason == AUTO_HIDE_REASON
        ):
            updates.update(
                status="published",
                hidden_reason="",
                hidden_at=None,
                hidden_by_id=None,
            )
        Moment.objects.filter(pk=moment.pk).update(**updates)

    for comment in Comment.objects.filter(pk__in=comment_ids).iterator():
        pending_count = Report.objects.filter(
            comment_id=comment.pk,
            status="pending",
        ).count()
        updates = {"report_count": pending_count}
        if pending_count >= threshold and comment.status == "visible":
            updates.update(status="hidden", review_note=AUTO_HIDE_REASON)
        elif (
            pending_count < threshold
            and comment.status == "hidden"
            and comment.review_note == AUTO_HIDE_REASON
        ):
            updates.update(status="visible", review_note="")
        Comment.objects.filter(pk=comment.pk).update(**updates)


def deduplicate_reports(apps, schema_editor):
    Report = apps.get_model("wiki", "MomentReport")
    affected_moment_ids = set()
    affected_comment_ids = set()
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
        rows = list(
            reports.values("id", "moment_id", "comment_id", "target_type")
        )
        keep_id = rows[0]["id"]
        affected_moment_ids.update(
            row["moment_id"] for row in rows if row["moment_id"]
        )
        affected_comment_ids.update(
            row["comment_id"]
            for row in rows
            if row["target_type"] == "comment" and row["comment_id"]
        )
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

    repair_report_derivatives(
        apps,
        moment_ids=affected_moment_ids,
        comment_ids=affected_comment_ids,
    )


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
