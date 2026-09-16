from django.db import migrations, models
import django.db.models.deletion


def set_safe_default_limits(apps, schema_editor):
    Config = apps.get_model("wiki", "AssistantProviderConfig")
    Config.objects.filter(daily_request_limit=0).update(daily_request_limit=100)
    Config.objects.filter(daily_token_limit=0).update(daily_token_limit=200000)


class Migration(migrations.Migration):
    dependencies = [("wiki", "0072_secure_survey_draft_identity")]

    operations = [
        migrations.AlterField(
            model_name="assistantproviderconfig",
            name="daily_request_limit",
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.AlterField(
            model_name="assistantproviderconfig",
            name="daily_token_limit",
            field=models.PositiveIntegerField(default=200000),
        ),
        migrations.RunPython(set_safe_default_limits, migrations.RunPython.noop),
        migrations.CreateModel(
            name="AssistantDailyUsage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("day", models.DateField(db_index=True)),
                ("request_count", models.PositiveIntegerField(default=0)),
                ("token_count", models.PositiveBigIntegerField(default=0)),
                (
                    "config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_usage_rows",
                        to="wiki.assistantproviderconfig",
                    ),
                ),
            ],
            options={
                "ordering": ["-day", "config_id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("config", "day"),
                        name="assistant_daily_usage_unique",
                    )
                ],
            },
        ),
    ]
