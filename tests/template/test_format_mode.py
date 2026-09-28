# -*- coding: utf-8 -*-
import pytest

from bamboo_engine.config import Settings
from bamboo_engine.template import Template
from bamboo_engine.utils import mako_safety
from bamboo_engine.utils.mako_utils.checker import check_mako_template_safety
from bamboo_engine.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
def test_format_renders_only_outside_enforce(monkeypatch, mode):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    template = "${pattern.format(name)}"
    assert Template(template).render({"pattern": "gamedb.{}.xzj.db", "name": "zone1"}) == (
        template if mode == "enforce" else "gamedb.zone1.xzj.db"
    )


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
def test_format_map_and_custom_filters_stay_blocked(monkeypatch, mode):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    for template in ("${pattern.format_map(values)}", "${name | custom}"):
        assert (
            Template(template).render({"pattern": "{name}", "values": {"name": "prod"}, "name": "prod", "custom": str})
            == template
        )


@pytest.mark.parametrize("payload", ['${"{0.__class__}".format("")}', "${pattern.format}"])
def test_enforce_blocks_format_lookup_and_method_reference(payload):
    with pytest.raises(ForbiddenMakoTemplateException):
        check_mako_template_safety(
            payload,
            mako_safety.WhitelistNameVisitor({"pattern"}, mode="enforce"),
            mako_safety.SingleLinCodeExtractor(),
        )
