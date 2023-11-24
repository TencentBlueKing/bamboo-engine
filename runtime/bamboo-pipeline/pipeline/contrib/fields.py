# -*- coding: utf-8 -*-
import codecs
import json
import pickle

from django.db.models import TextField


class SerializerField(TextField):
    """
    特定的序列化类，用于兼容json和pickle两种序列化数据
    """

    def to_python(self, value):
        try:
            return json.loads(value)
        except Exception:
            return pickle.loads(codecs.decode(value.encode(), "base64"))

    def from_db_value(self, value, expression, connection, context=None):
        try:
            return json.loads(value)
        except Exception:
            return pickle.loads(codecs.decode(value.encode(), "base64"))

    def get_prep_value(self, value):
        try:
            return json.dumps(value)
        except TypeError:
            return codecs.encode(pickle.dumps(value), "base64").decode()
        pass
