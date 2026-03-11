from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_default_team_member(apps, schema_editor):
    TeamMember = apps.get_model("wiki", "TeamMember")
    if TeamMember.objects.filter(display_id="Null_Resot").exists():
        return
    TeamMember.objects.create(
        display_id="Null_Resot",
        avatar_url="/wiki-assets/resot.png",
        profile_url="https://github.com/NullResot",
        is_active=True,
        sort_order=0,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0011_alter_issueticket_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeamMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("display_id", models.CharField(max_length=80)),
                ("avatar_url", models.CharField(blank=True, max_length=500)),
                ("profile_url", models.URLField(max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team_member",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.RunPython(seed_default_team_member, migrations.RunPython.noop),
    ]
