from __future__ import annotations

import unittest
from datetime import datetime

from clipforge.resource_limits import cpu_thread_budget
from clipforge.scheduling import schedule_window_is_open


class SchedulingTests(unittest.TestCase):
    def test_disabled_schedule_allows_jobs_at_any_time(self) -> None:
        self.assertTrue(schedule_window_is_open({"processing_schedule_enabled": False}, datetime(2026, 11, 23, 3, 0)))

    def test_regular_window_uses_selected_weekdays_and_half_open_boundaries(self) -> None:
        settings = {
            "processing_schedule_enabled": True,
            "processing_schedule_start": "09:00",
            "processing_schedule_end": "17:00",
            "processing_schedule_days": [0],
        }
        self.assertFalse(schedule_window_is_open(settings, datetime(2026, 11, 23, 8, 59)))
        self.assertTrue(schedule_window_is_open(settings, datetime(2026, 11, 23, 9, 0)))
        self.assertTrue(schedule_window_is_open(settings, datetime(2026, 11, 23, 16, 59)))
        self.assertFalse(schedule_window_is_open(settings, datetime(2026, 11, 23, 17, 0)))
        self.assertFalse(schedule_window_is_open(settings, datetime(2026, 11, 24, 12, 0)))

    def test_overnight_window_belongs_to_the_day_it_starts(self) -> None:
        settings = {
            "processing_schedule_enabled": True,
            "processing_schedule_start": "22:00",
            "processing_schedule_end": "06:00",
            "processing_schedule_days": [0],
        }
        self.assertTrue(schedule_window_is_open(settings, datetime(2026, 11, 23, 23, 30)))
        self.assertTrue(schedule_window_is_open(settings, datetime(2026, 11, 24, 5, 59)))
        self.assertFalse(schedule_window_is_open(settings, datetime(2026, 11, 24, 6, 0)))
        self.assertFalse(schedule_window_is_open(settings, datetime(2026, 11, 24, 23, 0)))

    def test_equal_times_mean_the_full_selected_day_and_invalid_settings_fail_closed(self) -> None:
        settings = {
            "processing_schedule_enabled": True,
            "processing_schedule_start": "08:30",
            "processing_schedule_end": "08:30",
            "processing_schedule_days": [2],
        }
        self.assertTrue(schedule_window_is_open(settings, datetime(2026, 11, 25, 0, 0)))
        self.assertFalse(schedule_window_is_open(settings, datetime(2026, 11, 26, 12, 0)))
        self.assertFalse(schedule_window_is_open({"processing_schedule_enabled": True}, datetime(2026, 11, 25, 12, 0)))

    def test_cpu_target_becomes_a_conservative_per_job_thread_budget(self) -> None:
        self.assertEqual(cpu_thread_budget(75, 16), 12)
        self.assertEqual(cpu_thread_budget(50, 3), 1)
        self.assertEqual(cpu_thread_budget(90, 1), 1)
        with self.assertRaises(ValueError):
            cpu_thread_budget(20, 16)


if __name__ == "__main__":
    unittest.main()
