"""Synthetic contract test only; no real ERP call or warranty decision."""
import unittest

class SavContract(unittest.TestCase):
    def test_retry_does_not_duplicate_synthetic_request(self):
        requests = {}
        def submit(customer, ticket):
            return requests.setdefault((customer, ticket), {'status': 'AWAITING_ERP'})
        first = submit('client-17', 'ticket-42')
        self.assertIs(first, submit('client-17', 'ticket-42'))
        self.assertEqual(len(requests), 1)
        self.assertEqual(first['status'], 'AWAITING_ERP')
