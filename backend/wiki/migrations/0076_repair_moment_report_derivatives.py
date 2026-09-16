from django.db import migrations, models
from django.utils import timezone


AUTO_HIDE_REASON = "举报达到阈值，系统已自动隐藏并等待人工复核。"


def _counts_by(queryset, field_name):
    return {
        row[field_name]: row["total"]
        for row in queryset.values(field_name).annotate(total=models.Count("id"))
        if row[field_name]
    }


def repair_report_derivatives(apps, schema_editor):
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

    pending_by_comment = _counts_by(
        Report.objects.filter(status="pending", comment_id__isnull=False),
        "comment_id",
    )
    for comment in Comment.objects.all().iterator():
        pending_count = int(pending_by_comment.get(comment.pk, 0))
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

    pending_by_moment = _counts_by(
        Report.objects.filter(status="pending", moment_id__isnull=False),
        "moment_id",
    )
    visible_comments_by_moment = _counts_by(
        Comment.objects.filter(status="visible"),
        "moment_id",
    )
    for moment in Moment.objects.all().iterator():
        pending_count = int(pending_by_moment.get(moment.pk, 0))
        visible_comment_count = int(visible_comments_by_moment.get(moment.pk, 0))
        updates = {
            "comment_count": visible_comment_count,
            "report_count": pending_count,
            "hot_score": (
                int(moment.like_count or 0) * like_weight
                + int(moment.favorite_count or 0) * favorite_weight
                + visible_comment_count * comment_weight
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


class Migration(migrations.Migration):
    dependencies = [("wiki", "0075_competition_notice_revision_base")]

    operations = [
        migrations.RunPython(
            repair_report_derivatives,
            migrations.RunPython.noop,
        ),
    ]
