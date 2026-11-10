"""Run the payment adapter's nonfinancial negative controls (fake PayPal provider, no network, no money) and record the
result for the evidence auditor:  python -B scripts/run_payment_negatives.py [out.json]

Requires `cryptography` (see paypal_adapter/requirements.lock).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "N07": ["tests.test_release_negatives.ReleaseNegatives.test_n07_duplicate_capture_single_post"],
    "N09": ["tests.test_gateway.GatewayTests.test_unknown_capture_approved_readback_does_not_retry"],
    "N10": ["tests.test_release_negatives.ReleaseNegatives.test_n10_payee_swapped_at_provider_no_capture",
            "tests.test_release_negatives.ReleaseNegatives.test_n10_approved_without_payer_identity_no_capture",
            "tests.test_gateway.GatewayTests.test_t08_unsigned_changed_amount_merchant"],
    "N14": ["tests.test_release_negatives.ReleaseNegatives.test_n14_capture_without_provider_approval_no_capture",
            "tests.test_approval.ApprovalTests.test_callback_does_not_replace_buyer_approval",
            "tests.test_approval.ApprovalTests.test_forged_callback_no_capture"],
}


def run(test):
    r = subprocess.run([sys.executable, "-B", "-m", "unittest", test], cwd=ROOT / "paypal_adapter", capture_output=True, text=True)
    return {"test": test, "pass": r.returncode == 0, "output_tail": (r.stdout + r.stderr).strip().splitlines()[-1:]}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo_evidence" / "PAYMENT_NEGATIVES.json"
    res = {cid: [run(t) for t in tests] for cid, tests in CASES.items()}
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provider": "FakePayPal (MOCK_ONLY; no network, no money)",
           "python": sys.version.split()[0], "cases": res, "all_pass": all(t["pass"] for v in res.values() for t in v)}
    out.write_text(json.dumps(doc, indent=1), newline="\n")
    print(json.dumps({k: all(t["pass"] for t in v) for k, v in res.items()} | {"all_pass": doc["all_pass"]}))
    return 0 if doc["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
