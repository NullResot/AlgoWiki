from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("wiki", "0070_ai_moderation_retry"),
    ]

    operations = [
        migrations.AddField(
            model_name="aimoderationconfig",
            name="topic_proposal_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="aimoderationrecord",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("comment", "Comment"),
                    ("question", "Question"),
                    ("answer", "Answer"),
                    ("ticket", "Ticket"),
                    ("moment", "Moment"),
                    ("moment_comment", "Moment Comment"),
                    ("pulse_topic_proposal", "Pulse Topic Proposal"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="PulseTopicProposal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=220)),
                ("content_md", models.TextField()),
                ("tags", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("ai_pending", "AI Pending"), ("admin_pending", "Admin Pending"), ("scheduled", "Scheduled"), ("rejected", "Rejected")], db_index=True, default="ai_pending", max_length=20)),
                ("review_note", models.CharField(blank=True, max_length=300)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("scheduled_date", models.DateField(blank=True, db_index=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pulse_topic_proposals", to=settings.AUTH_USER_MODEL)),
                ("edition", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="topic_proposal", to="wiki.pulsedailyedition")),
                ("reviewer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_pulse_topic_proposals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
