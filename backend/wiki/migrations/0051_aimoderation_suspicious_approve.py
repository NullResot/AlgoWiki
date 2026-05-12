from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0050_move_friendly_links_to_documents"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aimoderationconfig",
            name="suspicious_action",
            field=models.CharField(
                choices=[
                    ("pending", "Keep Pending"),
                    ("approve", "Approve"),
                    ("reject", "Reject"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
