from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0053_moments_v1"),
    ]

    operations = [
        migrations.AddField(
            model_name="realnameverification",
            name="provider_order_no",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_certify_id",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_scene_id",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_sub_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_status_message",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_device_risk",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_result",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_callback_token",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="realnameverification",
            name="provider_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
