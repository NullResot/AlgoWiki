from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wiki", "0069_pulse_audit_events"),
    ]

    operations = [
        migrations.AddField(
            model_name="aimoderationrecord",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aimoderationrecord",
            name="content_fingerprint",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="aimoderationrecord",
            name="last_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="aimoderationrecord",
            name="next_retry_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="aimoderationrecord",
            name="retry_state",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("finished", "Finished"),
                ],
                db_index=True,
                default="finished",
                max_length=20,
            ),
        ),
    ]
