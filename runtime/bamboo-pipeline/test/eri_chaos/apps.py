from django.apps import AppConfig


class EriChaosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eri_chaos"

    def ready(self):
        from .celery_tasks import chaos_execute, chaos_schedule  # noqa