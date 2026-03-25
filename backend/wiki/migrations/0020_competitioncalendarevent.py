import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0019_alter_answer_status_alter_question_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitionCalendarEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_site",
                    models.CharField(
                        choices=[
                            ("codeforces", "Codeforces"),
                            ("atcoder", "AtCoder"),
                            ("nowcoder", "牛客"),
                            ("luogu", "洛谷"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("source_id", models.CharField(db_index=True, max_length=120)),
                ("title", models.CharField(max_length=300)),
                ("organizer", models.CharField(blank=True, max_length=200)),
                ("url", models.URLField(max_length=500)),
                ("start_time", models.DateTimeField(db_index=True)),
                ("end_time", models.DateTimeField(db_index=True)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("last_synced_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("extra", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["start_time", "source_site", "source_id"],
            },
        ),
        migrations.AddIndex(
            model_name="competitioncalendarevent",
            index=models.Index(fields=["source_site", "start_time"], name="wiki_compet_source__39905d_idx"),
        ),
        migrations.AddIndex(
            model_name="competitioncalendarevent",
            index=models.Index(fields=["end_time"], name="wiki_compet_end_tim_d77750_idx"),
        ),
        migrations.AddConstraint(
            model_name="competitioncalendarevent",
            constraint=models.UniqueConstraint(
                fields=("source_site", "source_id"),
                name="unique_competition_calendar_event_source",
            ),
        ),
    ]
