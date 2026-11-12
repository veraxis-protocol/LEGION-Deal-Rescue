"""CAD-027 offline tests (always run, no external inputs). The real STEP/ZTL tests are in
tests/judge_real_cad027.py: they never skip and are run by Judge Mode and the judge-e2e CI job."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from deal_rescue.industrial import cad027_review as R, cad_xcaf, ztl_gate

STEP = os.environ.get("CAD027_STEP", "")
README = os.environ.get("CAD027_README", "")
PERF = os.environ.get("CAD027_PERF", "")
ZTL = os.environ.get("ZTL_ENGINEER_DIR", "")
HAVE_REAL = Path(STEP).is_file() and Path(README).is_file() and Path(PERF).is_file()
HAVE_ZTL = Path(ZTL, "mcp_server.py").is_file()
try:
    import OCP  # noqa: F401
    HAVE_OCP = True
except ImportError:
    HAVE_OCP = False

MINI_README = """## 🖨️ 3D Printed Parts

| Part Description | Image | File Name | Material | Qty | Notes |
|----------|------|--------|------|----------|------|
| Finger | x | 01_Finger.step | Bambu ABS Black | 2 | 0.4 nozzle |
| - | Reference Price | Average **50$** | | | |

| Part Description | Image | File Name | Material | Qty | Remarks |
| ---- | ---- | ---- | ---- | ---- | ---- |
| Wiring Harness Clips for Two Sides of Motor 1 | x | `DM_Motor1_wiring_harness_clip.stp` | ABS | 2 | 0.4 mm nozzle |

## 🔩 CNC Machined Metal Parts

| Part Description | Image | File Name | Material | Qty | Machining | Notes |
|----------|------|--------|----------|------|------|------|
| Rack | x | 02_Rack.step | Aluminum Alloy 5052 | 2 | CNC | |

### 🧩 Machining Specifications
- Key dimension tolerance: ±0.02 mm GB/T1840-M

## 🛒 Purchased Parts (Standard Parts)

  | Name | Specification / Model | Quantity | Reference Price | Notes |
  |------|----------|------|----------|------|
  | Linear rail | MGN9-170mm | 1 | 23 $/unit | x |
"""
MINI_PERF = """1. **Recommended Working Conditions**
   - Load: < 1.5 kg
   - Working radius: < 70% reach (450 mm)
<p align="center">Damiao 43 Series Motor 12Nm Load Curve</p>
"""
MINI_XCAF = {"file": "mini.step", "sha256": "a" * 64, "length_unit": "mm",
             "instances": {"01_Finger": 2, "02_Rack": 2, "RAIL-170": 1, "KM3-7": 64},
             "geometry": {"01_Finger": {"solids": 1, "faces": 10, "bbox": [1, 2, 3], "volume": 1.0},
                          "02_Rack": {"solids": 1, "faces": 10, "bbox": [90, 6, 12], "volume": 1.0},
                          "RAIL-170": {"solids": 1, "faces": 47, "bbox": [9.0, 6.5, 170.0], "volume": 1.0}}}
TEST_ONLY_TOL = ((-0.02, 0.02), "TEST SCENARIO ONLY: synthetic tolerance, not a reBot source")


def bom(xcaf=MINI_XCAF, text=MINI_README):
    return R.reconcile(xcaf, R.parse_readme(text), "b" * 64)


class Offline(unittest.TestCase):
    def test_bom_matches_source(self):
        b = bom()
        self.assertEqual((b["mandatory_positions"], b["mandatory_positions_matched"]), (2, 2))
        self.assertEqual(b["mandatory_instances_step"], b["mandatory_instances_readme"])
        self.assertEqual(R.bom_status(b), "T")
        self.assertEqual(b["optional"][0]["step_quantity"], 0)          # optional shown separately, not mandatory
        self.assertIn("KM3-7", b["purchased_and_fasteners_in_step"])     # fasteners listed, not force-matched

    def test_quantity_change_gives_F(self):
        x = copy.deepcopy(MINI_XCAF)
        x["instances"]["02_Rack"] = 3
        b = bom(x)
        self.assertEqual(R.bom_status(b), "F")
        self.assertIn({"part_id": "02_RACK", "readme": 2, "step": 3}, b["mismatches"])

    def test_material_or_tolerance_change_detected(self):
        base = R.cad025_spec(bom(), "a" * 64, "b" * 64)
        changed = R.cad025_spec(bom(text=MINI_README.replace("Aluminum Alloy 5052", "Aluminum Alloy 6061")), "a" * 64, "b" * 64)
        self.assertNotEqual(ztl_gate.spec_digest(base), ztl_gate.spec_digest(changed))
        tol = copy.deepcopy(base)
        tol["bom"][1]["dimensional_tolerances"] = "+-0.05 mm"
        self.assertNotEqual(ztl_gate.spec_digest(base), ztl_gate.spec_digest(tol))

    def test_unconfirmed_tolerance_gives_Z(self):
        with self.assertRaises(R.ToleranceUnsupported):
            R.rail_length_brick(MINI_XCAF, MINI_README)                  # no sourced tolerance -> no brick
        rail = R.production_predicates(MINI_XCAF, MINI_README, MINI_PERF)[0]
        self.assertEqual((rail["RAIL_TOLERANCE"], rail["verdict"], rail["stand_called"]), ("Z", "OPEN", False))
        only = rail["tolerance"]["only_tolerance_in_sources"]
        self.assertIn("±0.02 mm GB/T1840-M", only["text"])
        self.assertFalse(only["applies_to_purchased_rail"])

    def test_step_rounding_is_not_manufacturing_precision(self):
        rail = R.production_predicates(MINI_XCAF, MINI_README, MINI_PERF)[0]
        self.assertIn("not manufacturing precision", rail["inputs"]["L_cad"]["source"])
        brick = R.rail_length_brick(MINI_XCAF, MINI_README, *TEST_ONLY_TOL)
        self.assertEqual(brick["quantities"]["L_cad"]["value"], "170.000")   # nominal, exact: no invented spread
        self.assertNotIn("range", brick["quantities"]["L_cad"])

    def test_no_production_predicate_earned_without_stand(self):
        for p in R.production_predicates(MINI_XCAF, MINI_README, MINI_PERF):
            self.assertNotEqual(p["verdict"], "EARNED")
            self.assertTrue(p["missing"])
            for v in p.get("inputs", {}).values():
                self.assertTrue(v["source"])

    def test_changed_requirement_detected(self):
        d0 = R.requirements_digest(R.production_predicates(MINI_XCAF, MINI_README, MINI_PERF))
        d1 = R.requirements_digest(R.production_predicates(MINI_XCAF, MINI_README, MINI_PERF.replace("1.5 kg", "2.5 kg")))
        d2 = R.requirements_digest(R.production_predicates(MINI_XCAF, MINI_README.replace("MGN9-170mm", "MGN9-150mm"), MINI_PERF))
        self.assertNotEqual(d0, d1)
        self.assertNotEqual(d0, d2)

    def test_rerun_identical_verdicts_offline(self):
        a = R.production_predicates(MINI_XCAF, MINI_README, MINI_PERF)
        b = R.production_predicates(copy.deepcopy(MINI_XCAF), MINI_README, MINI_PERF)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_no_values_are_invented(self):
        finger = next(r for r in bom()["rows"] if r["part_id"] == "01_FINGER")
        self.assertIsNone(finger["tolerances"])                          # printed part: readme states none
        self.assertIn("dimensional_tolerances", finger["missing_requirements"])

    def test_incomplete_spec_blocks_admission(self):
        out = R.cad025_gate(R.cad025_spec(bom(), "a" * 64, "b" * 64), {"production_verdict": "OPEN"})
        self.assertEqual(out["engineering_admission"], "Z")
        self.assertEqual(out["spec_validation"]["status"], "REFUSED")

    def test_unsigned_ztl_result_blocks_admission(self):
        # Spec complete enough to pass validation; verifier configured with a TEST key generated here (never shipped).
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        src = "c" * 64
        spec = {"drawing_sha256": src, "drawing_revision": "r1",
                "source_documents": [{"document_id": "d", "kind": "step", "sha256": src}],
                "bom": [{"part_number": "P1", "quantity": 1, "source_sha256": src,
                         **{f: "stated" for f in ztl_gate.PART_FIELDS}}],
                "requirements": [{"id": f"P1.{c}", "part_number": "P1", "category": c, "statement": "s",
                                  "source_sha256": src} for c in sorted(ztl_gate.CATEGORIES)]}
        pem = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        env = {"LEGION_ZTL_ATTESTATION_URL": "https://verifier.example.com/attest", "LEGION_BACKEND_TOKEN": "t",
               "LEGION_ZTL_VERIFY_KEY_PEM": pem, "LEGION_ZTL_VERIFY_KID": "k1", "LEGION_ZTL_CURRENT_EPOCH": "1",
               "LEGION_ZTL_POLICY_SHA256": "d" * 64, "LEGION_ZTL_STAND_COMMIT": "e" * 40}
        out = R.cad025_gate(spec, {"verdict": "EARNED"}, env=env)   # stub verifier returns attestation_jws=None
        self.assertEqual(out["spec_validation"]["status"], "VALID")
        self.assertEqual(out["admission"], "F")
        self.assertNotEqual(out["engineering_admission"], "T")

    def test_sha_substitution_gives_F(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / R.PINNED_STEP_NAME
            fake.write_bytes(b"ISO-10303-21;\nEND-ISO-10303-21;\n")
            with self.assertRaises(cad_xcaf.SourceMismatch):
                cad_xcaf.read_assembly(fake, R.PINNED_STEP_SHA256)
            readme = Path(d) / "readme.md"
            readme.write_text(MINI_README, encoding="utf-8")
            r = R.StagedRun(fake, readme, None).stage(4)
            self.assertEqual(r["drawing"]["status"], "F")
            self.assertNotIn("xcaf", r)
            self.assertEqual(r["overall"]["demo"], "F")

    def test_demo_go_is_not_engineering_admission(self):
        report = {"drawing": {"status": "T"}, "bom_status": "T",
                  "ztl": {"production_verdict": "OPEN", "predicates": [{"verdict": "OPEN"}],
                          "integration_test": {"stand_called": True}},
                  "cad025": {"engineering_admission": "Z"}}
        self.assertEqual(R.demo_status(report), "T")
        bad = copy.deepcopy(report)
        bad["ztl"]["predicates"] = [{"verdict": "EARNED", "stand_called": False}]   # EARNED without the stand
        self.assertEqual(R.demo_status(bad), "F")


if __name__ == "__main__":
    unittest.main()
