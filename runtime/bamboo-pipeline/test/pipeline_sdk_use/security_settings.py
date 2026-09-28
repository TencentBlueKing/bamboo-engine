"""Local/CI security regressions: in-memory SQLite and no external service config."""
SECRET_KEY = "local-security-tests-only"
USE_TZ = True
USE_I18N = False
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "pipeline",
    "pipeline.log",
    "pipeline.engine",
    "pipeline.component_framework",
    "pipeline.variable_framework",
    "pipeline.django_signal_valve",
    "pipeline.contrib.rollback",
    "pipeline.contrib.plugin_execute",
    "pipeline.eri",
]
MIDDLEWARE = []
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
BROKER_URL = "memory://"
CELERY_BROKER_URL = "memory://"
PIPELINE_DATA_BACKEND = "pipeline.engine.core.data.mysql_backend.MySQLDataBackend"
MAKO_SAFETY_CHECK = True
MAKO_SANDBOX_IMPORT_MODULES = {}
