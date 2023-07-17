# -*- coding: utf-8 -*-
from django.conf import settings

from bamboo_engine.config import Settings
from bamboo_engine.utils.constants import RUNTIME_ALLOWED_CONFIG


class ConfigMixin:
    def get_config(self, name):
        if name not in RUNTIME_ALLOWED_CONFIG:
            raise ValueError("unsupported pipeline config, name={}".format(name))

        custom_config_value = getattr(settings, name, None)
        if custom_config_value:
            return custom_config_value
        return getattr(Settings, name)
