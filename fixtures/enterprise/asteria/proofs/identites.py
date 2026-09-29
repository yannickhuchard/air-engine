"""Synthetic time-window contract only; no IAM account is changed."""
import unittest

class IdentityContract(unittest.TestCase):
    def test_end_of_assignment_is_exclusive(self):
        def active(at, start, end, sponsored): return sponsored and start <= at < end
        self.assertTrue(active(99, 0, 100, True))
        self.assertFalse(active(100, 0, 100, True))
        self.assertFalse(active(10, 0, 100, False))
