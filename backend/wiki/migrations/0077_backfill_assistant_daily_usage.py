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
        DailyUsage.objects.update_or_create(
            config_id=usage["config_id"],
            day=day,
            defaults={
                "request_count": int(usage["request_count"] or 0),
                "token_count": int(usage["token_count"] or 0),
            },
        )


class Migration(migrations.Migration):
    dependencies = [("wiki", "0076_repair_moment_report_derivatives")]

    operations = [
        migrations.RunPython(
            backfill_assistant_daily_usage,
            migrations.RunPython.noop,
        ),
    ]
