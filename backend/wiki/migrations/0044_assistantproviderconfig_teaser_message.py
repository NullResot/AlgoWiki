from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wiki", "0043_sitevisitdailystat"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistantproviderconfig",
            name="teaser_message",
            field=models.TextField(blank=True),
        ),
    ]
