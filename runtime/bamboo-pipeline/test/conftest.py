from django.db.backends.base.base import BaseDatabaseWrapper
from pytest_django.plugin import _blocking_manager

_blocking_manager.unblock()
_blocking_manager._blocking_wrapper = BaseDatabaseWrapper.ensure_connection
