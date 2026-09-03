# -*- coding: utf-8 -*-
import ast

from bamboo_engine.utils.mako_safety import import_chain_violation, resolve_attr_chain


def _attr_node(expr):
    tree = ast.parse(expr, "<t>", "eval")
    node = tree.body
    while isinstance(node, ast.Call):
        node = node.func
    assert isinstance(node, ast.Attribute)
    return node


def test_resolve_attr_chain_name_two_levels():
    kind, root, attrs = resolve_attr_chain(_attr_node("json.codecs.builtins"))
    assert kind == "name"
    assert root == "json"
    assert attrs == ["codecs", "builtins"]


def test_resolve_attr_chain_stops_at_call():
    kind, root, attrs = resolve_attr_chain(_attr_node('datetime.datetime.now().strftime("%Y")'))
    assert kind == "call_result"
    assert root is None
    assert attrs == ["strftime"]


def test_import_json_loads_ok():
    aliases = frozenset(["json", "re", "os.path", "datetime", "datetime.datetime"])
    assert import_chain_violation("json", ["loads"], aliases) is None


def test_import_os_path_join_ok():
    aliases = frozenset(["os.path", "json"])
    assert import_chain_violation("os", ["path", "join"], aliases) is None


def test_import_os_popen_rejected():
    aliases = frozenset(["os.path"])
    reason = import_chain_violation("os", ["popen"], aliases)
    assert reason is not None


def test_import_json_codecs_builtins_rejected():
    aliases = frozenset(["json"])
    reason = import_chain_violation("json", ["codecs", "builtins"], aliases)
    assert reason is not None


def test_import_datetime_now_needs_class_alias():
    aliases = frozenset(["datetime"])
    assert import_chain_violation("datetime", ["datetime", "now"], aliases) is not None
    aliases = frozenset(["datetime", "datetime.datetime"])
    assert import_chain_violation("datetime", ["datetime", "now"], aliases) is None


def test_non_import_root_is_ignored():
    aliases = frozenset(["json"])
    assert import_chain_violation("resdata", ["_module"], aliases) is None
