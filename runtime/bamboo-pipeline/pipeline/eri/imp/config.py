# -*- coding: utf-8 -*-
from django.conf import settings

from bamboo_engine.config import Settings
from bamboo_engine.utils.constants import RUNTIME_ALLOWED_CONFIG


class ConfigMixin:
    def get_config(self, config_name):
        if config_name not in RUNTIME_ALLOWED_CONFIG:
            raise ValueError("unsupported config, name={}".format(config_name))

        custom_config_value = getattr(settings, config_name, None)
        if custom_config_value:
            return custom_config_value
        return getattr(Settings, config_name)
