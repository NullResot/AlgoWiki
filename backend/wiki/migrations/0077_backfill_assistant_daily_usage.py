from datetime import datetime, time, timedelta

from django.db import migrations, models
from django.db.models.functions import Coalesce
from django.utils import timezone


def backfill_assistant_daily_usage(apps, schema_editor):
    InteractionLog = apps.get_model("wiki", "AssistantInteractionLog")
    DailyUsage = apps.get_model("wiki", "AssistantDailyUsage")

    day = timezone.localdate()
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), current_timezone)
    end = start + timedelta(days=1)
    usage_by_config = (
        InteractionLog.objects.filter(
            config_id__isnull=False,
            created_at__gte=start,
            created_at__lt=end,
        )
        .values("config_id")
        .annotate(
            request_count=models.Count("id"),
            token_count=Coalesce(models.Sum("total_tokens"), 0),
        )
    )

    for usage in usage_by_config.iterator():
        usage_row, created = DailyUsage.objects.get_or_create(
            config_id=usage["config_id"],
            day=day,
            defaults={
                "request_count": int(usage["request_count"] or 0),
                "token_count": int(usage["token_count"] or 0),
            },
        )
        if created:
            continue
        # The row was created by the first atomic reservation after 0073. Its
        # counters already include every reservation from that point onward,
        # including requests whose interaction log was never written. Only
        # logs from before the row existed are legacy usage that must be added.
        cutoff = min(max(usage_row.created_at, start), end)
        legacy_usage = InteractionLog.objects.filter(
            config_id=usage["config_id"],
            created_at__gte=start,
            created_at__lt=cutoff,
        ).aggregate(
            request_count=models.Count("id"),
            token_count=Coalesce(models.Sum("total_tokens"), 0),
        )
        request_count = int(usage_row.request_count or 0) + int(
            legacy_usage["request_count"] or 0
        )
        token_count = int(usage_row.token_count or 0) + int(
            legacy_usage["token_count"] or 0
        )
        if (
            request_count != int(usage_row.request_count or 0)
            or token_count != int(usage_row.token_count or 0)
        ):
            DailyUsage.objects.filter(pk=usage_row.pk).update(
                request_count=request_count,
                token_count=token_count,
            )


class Migration(migrations.Migration):
    dependencies = [("wiki", "0076_repair_moment_report_derivatives")]

    operations = [
        migrations.RunPython(
            backfill_assistant_daily_usage,
            migrations.RunPython.noop,
        ),
    ]
