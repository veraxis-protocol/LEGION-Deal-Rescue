"""Release acceptance tests for LEGION Deal Rescue (stdlib unittest; no network, no PayPal, no model calls).

python -B -m unittest discover -s tests -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dr_"))
        cls.ev = cls.tmp / "ev"
        shutil.copytree(ROOT / "demo_evidence", cls.ev, ignore=shutil.ignore_patterns("dossier"))
        r = subprocess.run([sys.executable, "-B", "scripts/build_and_serve.py", "--evidence", str(cls.ev), "--no-serve"],
                           cwd=ROOT, capture_output=True, text=True)
        cls.out = r.stdout + r.stderr
        cls.rc = r.returncode

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def load(self, *p):
        return json.loads(self.ev.joinpath(*p).read_text())

    def test_build_and_audit_pass(self):
        self.assertEqual(self.rc, 0, self.out)
        for rid, v in self.load("UI_PROVENANCE_AUDIT.json").items():
            self.assertTrue(v["provenance"]["pass"], rid)
            self.assertEqual(v["provenance"]["coverage_pct"], 100.0, rid)
            self.assertTrue(v["claims"]["pass"], rid)
            self.assertEqual(v["mission_status"], "SIMULATED_MISSION_VERIFIED", rid)

    def test_judge_and_scenario_facts(self):
        for rid in ("WO004-A2-fresh-1", "WO004-A2-fresh-2"):
            d = self.load("dossier", rid, "DEAL_DOSSIER.json")
            self.assertEqual(d["judge"]["verdict"], "PASS_COMPLETED")
            self.assertEqual(d["judge"]["checks_passed"], d["judge"]["checks_total"])
            self.assertTrue(d["judge"]["evidence_hashes_match_rendered_files"])
            self.assertTrue(all(m["detected"] for m in d["judge"]["tamper_mutants"].values()))
            v = {t["version"]: t for t in d["terms_versions"]}
            self.assertEqual((v[1]["total_cents"], v[2]["total_cents"], v[3]["total_cents"]), (48000, 54000, 49500))
            self.assertEqual(v[2]["final_state"], "FAILED")
            self.assertEqual(sum(k["decision"] == "REJECT" for k in v[2]["commitments"]), 5)
            self.assertEqual(sum(k["decision"] == "ACCEPT" for k in v[3]["commitments"]), 7)
            self.assertEqual([r["design"] for r in d["rejected_designs"]], ["D-C"])
            self.assertTrue(all(x["mode"] == "SIMULATED" for x in d["execution"]))

    def test_paypal_truth(self):
        d = self.load("dossier", "WO004-A2-fresh-2", "DEAL_DOSSIER.json")
        p = d["paypal"]
        self.assertEqual((p["readback_confirmed_captures"], p["provider_confirmed_cents"]), (1, 9900))
        b1 = p["slots"][0]
        self.assertEqual((b1["owner_id"], b1["state"], b1["provider_confirmed_cents"]), ("owner:b1", "SANDBOX_PAYMENT_CONFIRMED", 9900))
        self.assertEqual(b1["contract_hash"], d["terms_versions"][-1]["contract_hash"])
        self.assertEqual(b1["readback"]["payment_status"], "VERIFIED_COMPLETED")
        self.assertEqual(b1["readback"]["captures_on_order"], 1)
        self.assertTrue(all(s["state"] == "NOT_AUTHORIZED" and s["provider_confirmed_cents"] == 0 for s in p["slots"][1:]))
        self.assertTrue(p["badge"].startswith("PAYPAL_PARTIAL_GO (1/5)"))
        # a payment bound to fresh-2's contract must NOT appear on fresh-1 (different contract hash)
        self.assertEqual(self.load("dossier", "WO004-A2-fresh-1", "DEAL_DOSSIER.json")["paypal"]["provider_confirmed_cents"], 0)
        led = self.load("paypal_runs", "lmf007-20261109T232734Z", "LEDGER_EXPORT.json")
        self.assertEqual(led["network_posts"], 2)   # one create + one capture, no retry
        self.assertEqual(len(led["effects"]), 1)

    def test_economics_honest(self):
        e = self.load("ECONOMIC_CASE.json")
        self.assertEqual(e["gross_contribution_before_overhead_cents"], 0)
        self.assertLess(e["net_contribution_upper_bound_cents"], 0)
        self.assertFalse(e["Commercial_GO"])
        self.assertTrue(self.load("HYPOTHETICAL_BREAK_EVEN.json")["exceeds_each_buyer_cap"])

    def test_negative_matrix(self):
        n = self.load("NEGATIVE_TESTS.json")["summary"]
        self.assertEqual(n["failed"], [])
        self.assertEqual(sorted(n["blocked"]), ["N10", "N14"])
        self.assertEqual(n["harness"], {"forbidden_effects": 0, "passed": 25, "total": 25})


if __name__ == "__main__":
    unittest.main()
