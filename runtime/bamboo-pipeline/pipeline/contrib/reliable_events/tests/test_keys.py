# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from pipeline.contrib.reliable_events import keys


class KeyTest(SimpleTestCase):
    def test_idempotency_key_for_callback(self):
        self.assertEqual(keys.idempotency_key_for_callback(42), "callback:42")

    def test_concurrency_key_for_node(self):
        self.assertEqual(keys.concurrency_key_for_node("node-1", "v1"), "node-1:v1")

    def test_payload_ref_for_callback(self):
        self.assertEqual(keys.payload_ref_for_callback(42), "eri_callbackdata:42")

    def test_payload_digest_stable_and_order_insensitive(self):
        a = keys.payload_digest({"x": 1, "y": 2})
        b = keys.payload_digest({"y": 2, "x": 1})
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_payload_digest_accepts_non_dict(self):
        self.assertEqual(len(keys.payload_digest("raw-string")), 64)
