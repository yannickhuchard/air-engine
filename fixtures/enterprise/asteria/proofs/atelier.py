"""Synthetic input contract only; no sensor reading or machine command."""
import unittest

class WorkshopContract(unittest.TestCase):
    def test_stale_measurement_cannot_clear_inspection(self):
        def assess(value, unit, age_seconds):
            if unit != 'mm/s' or age_seconds > 300: return 'UNKNOWN'
            return 'INSPECT' if value >= 7 else 'MONITOR'
        self.assertEqual(assess(2, 'mm/s', 301), 'UNKNOWN')
        self.assertEqual(assess(8, 'mm/s', 10), 'INSPECT')
        self.assertEqual(assess(2, 'rpm', 10), 'UNKNOWN')
