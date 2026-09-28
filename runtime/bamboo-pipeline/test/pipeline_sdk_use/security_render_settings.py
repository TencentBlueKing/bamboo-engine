"""Django-free application registry for cross-version Mako rendering regressions."""

SECRET_KEY = "local-render-security-regression"
INSTALLED_APPS = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
USE_I18N = False
MAKO_SAFETY_CHECK = True
