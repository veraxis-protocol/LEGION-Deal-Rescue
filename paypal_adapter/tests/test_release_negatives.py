"""Release negative controls for the payment path (fake provider only; no network, no money).

N10  payee/payer substitution: a provider order whose payee is not the mission's merchant, or an APPROVED order
     without a payer identity, must never be captured.
N14  approval callback without provider APPROVED: no capture.
N07  duplicate capture of the same effect: at most one capture POST.
"""
import tempfile
import unittest

from commerce_adapter.contracts import Denied
from tests.helpers import Fixture


def capture_posts(f):
    return f.provider.capture_count()


class ReleaseNegatives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = Fixture(self.tmp.name)

    def tearDown(self):
        self.f.gateway = None
        self.tmp.cleanup()

    def attempt_capture(self, eid):
        try:
            return self.f.gateway.capture(eid)
        except Denied as error:
            return f"DENIED:{error}"

    def test_n10_payee_swapped_at_provider_no_capture(self):
        eid = self.f.create()
        self.f.provider.approve()

        def swap_payee(path, result):
            if "/v2/checkout/orders/" in path and "purchase_units" in result:
                result["purchase_units"][0]["payee"] = {"merchant_id": "ATTACKER"}
        self.f.provider.tamper = swap_payee
        state = self.attempt_capture(eid)
        self.assertNotEqual(state, "CAPTURE_CONFIRMED")
        self.assertEqual(capture_posts(self.f), 0)

    def test_n10_approved_without_payer_identity_no_capture(self):
        eid = self.f.create()
        for order in self.f.provider.orders.values():
            order["status"] = "APPROVED"          # no payer identity attached
        state = self.attempt_capture(eid)
        self.assertNotEqual(state, "CAPTURE_CONFIRMED")
        self.assertEqual(capture_posts(self.f), 0)

    def test_n14_capture_without_provider_approval_no_capture(self):
        eid = self.f.create()                     # buyer never approved at the provider
        state = self.attempt_capture(eid)
        self.assertNotEqual(state, "CAPTURE_CONFIRMED")
        self.assertEqual(capture_posts(self.f), 0)

    def test_n07_duplicate_capture_single_post(self):
        eid = self.f.create()
        self.f.provider.approve()
        self.assertEqual(self.attempt_capture(eid), "CAPTURE_CONFIRMED")
        self.attempt_capture(eid)
        self.attempt_capture(eid)
        self.assertEqual(capture_posts(self.f), 1)


if __name__ == "__main__":
    unittest.main()
