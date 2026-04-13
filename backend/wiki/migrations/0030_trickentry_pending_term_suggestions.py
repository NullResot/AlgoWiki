from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		("wiki", "0029_trick_terms"),
	]

	operations = [
		migrations.AddField(
			model_name="trickentry",
			name="pending_term_suggestions",
			field=models.ManyToManyField(blank=True, related_name="pending_trick_entries", to="wiki.tricktermsuggestion"),
		),
	]