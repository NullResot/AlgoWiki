from django.apps import AppConfig


class WikiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wiki"
    verbose_name = "AlgoWiki Core"

    def ready(self):
        from . import signals  # noqa: F401
