"""REQUIRED real-input tests for CAD-027 (reBot STEP, OpenCascade XCAF, real ZTL stand). They never skip: if an input
is missing the module fails at import. Run by `python -m scripts.judge_demo` and the judge-e2e CI job with
CAD027_STEP, CAD027_README, CAD027_PERF and ZTL_ENGINEER_DIR set by the launcher (pinned, hash-verified inputs).
The file name does not match test*.py on purpose: plain `unittest discover` (no inputs) does not collect it."""
import copy
import json
import os
import unittest
from pathlib import Path

from deal_rescue.industrial import cad027_review as R, cad_xcaf
from tests.test_cad027_demo import MINI_README, MINI_XCAF, TEST_ONLY_TOL

STEP = os.environ.get("CAD027_STEP", "")
README = os.environ.get("CAD027_README", "")
PERF = os.environ.get("CAD027_PERF", "")
ZTL = os.environ.get("ZTL_ENGINEER_DIR", "")
_missing = [n for n, ok in (("CAD027_STEP", Path(STEP).is_file()), ("CAD027_README", Path(README).is_file()),
                            ("CAD027_PERF", Path(PERF).is_file()), ("ZTL_ENGINEER_DIR", Path(ZTL, "mcp_server.py").is_file()))
            if not ok]
if _missing:
    raise RuntimeError("REQUIRED_INPUT_MISSING (this suite never skips): " + ", ".join(_missing))
import OCP  # noqa: E402,F401  (ImportError here is a failure, not a skip)


class RealStand(unittest.TestCase):
    def test_integration_scenario_earned_and_labelled(self):
        t = R.integration_test_scenario(ZTL)
        self.assertEqual((t["label"], t["verdict"], t["stand_called"]), ("TEST_SCENARIO_NOT_REBOT", "EARNED", True))

    def test_test_tolerance_out_of_range_is_refuted(self):
        x = copy.deepcopy(MINI_XCAF)
        x["geometry"]["RAIL-170"]["bbox"] = [9.0, 6.5, 170.05]
        self.assertEqual(R.check_design(R.rail_length_brick(x, MINI_README, *TEST_ONLY_TOL), ZTL)["verdict"], "REFUTED")

    def test_tightened_test_tolerance_changes_verdict(self):
        x = copy.deepcopy(MINI_XCAF)
        x["geometry"]["RAIL-170"]["bbox"] = [9.0, 6.5, 170.001]
        self.assertEqual(R.check_design(R.rail_length_brick(x, MINI_README, *TEST_ONLY_TOL), ZTL)["verdict"], "EARNED")
        tight = R.rail_length_brick(x, MINI_README, (-0.0001, 0.0001), TEST_ONLY_TOL[1])
        self.assertEqual(R.check_design(tight, ZTL)["verdict"], "REFUTED")

    def test_unavailable_stand_is_explicit_not_pass(self):
        out = R.check_design(R.rail_length_brick(MINI_XCAF, MINI_README, *TEST_ONLY_TOL), str(Path(ZTL).parent / "absent"))
        self.assertEqual((out["verdict"], out["stand_called"]), ("OPEN", False))
        self.assertIn("ZTL_ENGINEER_NOT_FOUND", out["why"])


class RealStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = cad_xcaf.read_assembly(STEP, R.PINNED_STEP_SHA256)

    def test_step_opens_with_xcaf_structure(self):
        self.assertEqual(self.a["verdict"], "T_XCAF_STRUCTURE")
        self.assertEqual((self.a["assemblies"], self.a["leaf_definitions"], self.a["leaf_instances"]), (33, 64, 326))
        self.assertEqual(self.a["length_unit"], "mm")

    def test_bom_40_of_40_and_53_of_53(self):
        b = R.reconcile(self.a, R.parse_readme(Path(README).read_text(encoding="utf-8")), "b" * 64)
        self.assertEqual((b["mandatory_positions_matched"], b["mandatory_positions"]), (40, 40))
        self.assertEqual((b["mandatory_instances_step"], b["mandatory_instances_readme"]), (53, 53))
        self.assertEqual(b["purchased_readme_positions"], 27)
        self.assertEqual([(o["part_id"], o["quantity"], o["step_quantity"]) for o in b["optional"]],
                         [("DM_MOTOR1_WIRING_HARNESS_CLIP", 2, 0)])

    def test_rerun_reproduces_geometry(self):
        again = cad_xcaf.read_assembly(STEP, R.PINNED_STEP_SHA256)
        self.assertEqual(json.dumps(again["instances"], sort_keys=True), json.dumps(self.a["instances"], sort_keys=True))
        self.assertEqual(json.dumps(again["geometry"], sort_keys=True), json.dumps(self.a["geometry"], sort_keys=True))

    def test_full_run_scoped_verdicts_and_rerun_identical(self):
        def verdicts(r):
            return {**{k: r["overall"][k] for k in ("demo", "bom", "ztl_production", "rail_tolerance",
                                                     "ztl_integration_test", "engineering_admission")},
                    "digest": r["ztl"]["requirements_digest"], "cad025": r["cad025"].get("admission_code"),
                    "preds": [(p["id"], p["verdict"]) for p in r["ztl"]["predicates"]]}
        r1, r2 = (R.run(STEP, README, ZTL, PERF) for _ in range(2))
        self.assertEqual(verdicts(r1), verdicts(r2))
        v = verdicts(r1)
        self.assertEqual((v["demo"], v["ztl_production"], v["rail_tolerance"], v["engineering_admission"]), ("T", "OPEN", "Z", "Z"))
        self.assertEqual(v["preds"], [("rail_length_tolerance", "OPEN"), ("joint2_load_torque", "OPEN")])
        self.assertEqual(r1["overall"]["external_effects"], {"supplier_requests": 0, "paypal_calls": 0, "cad_transmitted": 0})


if __name__ == "__main__":
    unittest.main()
