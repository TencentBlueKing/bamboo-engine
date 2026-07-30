# -*- coding: utf-8 -*-
from django.db import connection
from django.test import TransactionTestCase

from pipeline.contrib.reliable_events.models import EngineEventInbox, EngineEventLane


class ReliableEventsTestCase(TransactionTestCase):
    models = (EngineEventInbox, EngineEventLane)

    @classmethod
    def setUpClass(cls):
        super(ReliableEventsTestCase, cls).setUpClass()
        cls._created_models = []
        try:
            with connection.schema_editor() as schema_editor:
                existing_tables = connection.introspection.table_names()
                for model in cls.models:
                    if model._meta.db_table not in existing_tables:
                        schema_editor.create_model(model)
                        cls._created_models.append(model)
        except Exception:
            cls._delete_created_models()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._delete_created_models()
        super(ReliableEventsTestCase, cls).tearDownClass()

    def tearDown(self):
        existing = connection.introspection.table_names()
        for model in reversed(self.models):
            if model._meta.db_table in existing:
                model.objects.all().delete()
        super(ReliableEventsTestCase, self).tearDown()

    @classmethod
    def _delete_created_models(cls):
        with connection.schema_editor() as schema_editor:
            for model in reversed(getattr(cls, "_created_models", [])):
                if model._meta.db_table in connection.introspection.table_names():
                    schema_editor.delete_model(model)
        cls._created_models = []
