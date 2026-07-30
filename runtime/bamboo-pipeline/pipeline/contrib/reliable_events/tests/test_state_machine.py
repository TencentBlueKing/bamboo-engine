# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from pipeline.contrib.reliable_events import state_machine as sm


class StateMachineTest(SimpleTestCase):
    def test_pending_to_processing(self):
        self.assertTrue(sm.validate_transition("PENDING", "PROCESSING", "SHADOW"))

    def test_processing_to_applied(self):
        self.assertTrue(sm.validate_transition("PROCESSING", "APPLIED", "SHADOW"))

    def test_processing_back_to_pending_retry(self):
        self.assertTrue(sm.validate_transition("PROCESSING", "PENDING", "SHADOW"))

    def test_shadow_mismatch_only_in_shadow(self):
        self.assertTrue(sm.validate_transition("PROCESSING", "SHADOW_MISMATCH", "SHADOW"))
        self.assertFalse(sm.validate_transition("PROCESSING", "SHADOW_MISMATCH", "ACTIVE"))

    def test_no_transition_out_of_terminal(self):
        self.assertFalse(sm.validate_transition("APPLIED", "PENDING", "SHADOW"))
        self.assertFalse(sm.validate_transition("OBSOLETE", "PROCESSING", "SHADOW"))

    def test_pending_to_manual_on_deadline(self):
        self.assertTrue(sm.validate_transition("PENDING", "MANUAL_REQUIRED", "ACTIVE"))
