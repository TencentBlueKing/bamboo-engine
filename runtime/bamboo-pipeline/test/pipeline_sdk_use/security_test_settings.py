"""Isolated SQLite settings for local/CI security and legacy regression tests.

No dotenv, deployment settings, network broker or environment-selected database is read.
"""

SECRET_KEY = "local-security-regression-only"
USE_I18N = False
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "pipeline_sdk_use.security_test_settings.OfflinePipelineConfig",
    "pipeline.log",
    "pipeline.engine",
    "pipeline.contrib.node_timer_event",
    "pipeline.component_framework",
    "pipeline.variable_framework",
    "pipeline.django_signal_valve",
    "pipeline.contrib.periodic_task",
    "pipeline.contrib.node_timeout",
    "pipeline.contrib.rollback",
    "pipeline.contrib.plugin_execute",
    "django_celery_beat",
    "pipeline_test_use",
    "variable_app",
    "pipeline.eri",
    "eri_chaos",
)
# Exercise current models; historical MySQL migrations are outside this suite.
MIGRATION_MODULES = {name.rsplit(".", 1)[-1]: None for name in INSTALLED_APPS}
MIGRATION_MODULES["pipeline"] = None
PIPELINE_DATA_BACKEND = "pipeline.engine.core.data.mysql_backend.MySQLDataBackend"
PIPELINE_DATA_CANDIDATE_BACKEND = None
MAKO_SAFETY_CHECK = True
ENABLE_EXAMPLE_COMPONENTS = True
BROKER_URL = "memory://"
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
STATIC_URL = "/static/"
PLUGIN_EXECUTE_QUEUE = "default"


class UnavailableRedis:
    """Fail explicitly if a test accidentally depends on a real Redis operation."""

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        raise RuntimeError("Redis is disabled in the isolated security test settings")


from pipeline.apps import PipelineConfig  # noqa: E402


class OfflinePipelineConfig(PipelineConfig):
    def ready(self):
        from django.conf import settings

        settings.redis_inst = settings.REDIS_INST = UnavailableRedis()
        super().ready()
