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


class Phase3ConfTest(TestCase):
    def test_scanners_disabled_by_default(self):
        self.assertFalse(conf.window_scan_enabled())
        self.assertFalse(conf.signature_scan_enabled())
        self.assertFalse(conf.callback_scan_enabled())

    def test_defaults(self):
        self.assertEqual(conf.window_tiers_seconds(), (3600, 86400))
        self.assertEqual(conf.signature_fast_threshold_seconds(), 300)
        self.assertEqual(conf.signature_slow_threshold_seconds(), 1800)
        self.assertEqual(conf.poll_exclude_codes(), frozenset())
        self.assertEqual(conf.signature_close_batch(), 500)
        self.assertEqual(conf.callback_confirm_seconds(), 120)
        self.assertEqual(conf.callback_pending_max_seconds(), 1800)
        self.assertEqual(conf.callback_pending_limit(), 5000)
        self.assertEqual(conf.callback_max_rows(), 5000)
        self.assertEqual(conf.scan_page_size(), 500)
        self.assertEqual(conf.scan_max_rows(), 20000)
        self.assertEqual(conf.window_max_roots(), 1000)
        self.assertEqual(conf.scan_initial_lookback_seconds(), 3600)

    @override_settings(
        PIPELINE_DIAGNOSTICS_WINDOW_TIERS="86400, 3600",
        PIPELINE_DIAGNOSTICS_POLL_EXCLUDE_CODES="sleep_timer, demo_poll",
    )
    def test_string_settings_are_parsed(self):
        self.assertEqual(conf.window_tiers_seconds(), (3600, 86400))
        self.assertEqual(conf.poll_exclude_codes(), frozenset(["sleep_timer", "demo_poll"]))

    @override_settings(PIPELINE_DIAGNOSTICS_POLL_EXCLUDE_CODES=["sleep_timer"], PIPELINE_DIAGNOSTICS_WINDOW_TIERS=[600])
    def test_sequence_settings_are_accepted(self):
        self.assertEqual(conf.poll_exclude_codes(), frozenset(["sleep_timer"]))
        self.assertEqual(conf.window_tiers_seconds(), (600,))
