from django.test import TestCase, override_settings

from pipeline.contrib.diagnostics import conf


class ConfDefaultsTest(TestCase):
    def test_stall_defaults(self):
        self.assertEqual(conf.stall_threshold_seconds(), 1800)
        self.assertEqual(conf.scan_batch(), 200)
        self.assertEqual(conf.second_confirm_seconds(), 3)
        self.assertEqual(conf.scan_max_silent_seconds(), 7 * 24 * 3600)

    @override_settings(PIPELINE_DIAGNOSTICS_SCAN_MAX_SILENT_SECONDS=0)
    def test_max_silent_can_be_disabled(self):
        self.assertEqual(conf.scan_max_silent_seconds(), 0)

    def test_apply_disabled_by_default(self):
        self.assertFalse(conf.apply_enabled())

    @override_settings(PIPELINE_DIAGNOSTICS_STALL_THRESHOLD_SECONDS=60)
    def test_override(self):
        self.assertEqual(conf.stall_threshold_seconds(), 60)
