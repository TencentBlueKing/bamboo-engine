# -*- coding: utf-8 -*-
import datetime as dt

from bamboo_engine.template.sandbox import ModuleObject, _import_modules, resolve_import_object


def test_resolve_import_object_module():
    import json

    assert resolve_import_object("json") is json


def test_resolve_import_object_class_path():
    assert resolve_import_object("datetime.datetime") is dt.datetime


def test_dotted_alias_does_not_clobber_existing_module():
    sandbox = {}
    _import_modules(
        sandbox,
        {
            "datetime": "datetime",
            "datetime.datetime": "datetime.datetime",
        },
    )
    assert sandbox["datetime"] is dt
    assert sandbox["datetime"].datetime is dt.datetime
    assert sandbox["datetime"].timedelta is dt.timedelta
    assert not isinstance(sandbox["datetime"], ModuleObject)


def test_os_path_still_uses_module_object():
    sandbox = {}
    _import_modules(sandbox, {"os.path": "os.path"})
    assert isinstance(sandbox["os"], ModuleObject)
    assert hasattr(sandbox["os"], "path")
    assert not hasattr(sandbox["os"], "popen")
