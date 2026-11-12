"""CAD-027 demo tests. Tests marked REAL need the local reBot STEP/readme (not in the repo, 34.8 MB) and the
ztl-engineer checkout:  CAD027_STEP, CAD027_README, ZTL_ENGINEER_DIR. Without them they are skipped, never faked."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from deal_rescue.industrial import cad027_review as R, cad_xcaf, ztl_gate

STEP = os.environ.get("CAD027_STEP", "")
README = os.environ.get("CAD027_README", "")
ZTL = os.environ.get("ZTL_ENGINEER_DIR", "")
HAVE_REAL = Path(STEP).is_file() and Path(README).is_file()
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

## 🛒 Purchased Parts (Standard Parts)

  | Name | Specification / Model | Quantity | Reference Price | Notes |
  |------|----------|------|----------|------|
  | Linear rail | MGN9-170mm | 1 | 23 $/unit | x |
"""
MINI_XCAF = {"file": "mini.step", "sha256": "a" * 64, "length_unit": "mm",
             "instances": {"01_Finger": 2, "02_Rack": 2, "RAIL-170": 1, "KM3-7": 64},
             "geometry": {"01_Finger": {"solids": 1, "faces": 10, "bbox": [1, 2, 3], "volume": 1.0},
                          "02_Rack": {"solids": 1, "faces": 10, "bbox": [90, 6, 12], "volume": 1.0},
                          "RAIL-170": {"solids": 1, "faces": 47, "bbox": [9.0, 6.5, 170.0], "volume": 1.0}}}


class Offline(unittest.TestCase):
    def bom(self, xcaf=MINI_XCAF, text=MINI_README):
        return R.reconcile(xcaf, R.parse_readme(text), "b" * 64)

    def test_bom_matches_source(self):
        b = self.bom()
        self.assertEqual((b["mandatory_positions"], b["mandatory_positions_matched"]), (2, 2))
        self.assertEqual(b["mandatory_instances_step"], b["mandatory_instances_readme"])
        self.assertEqual(b["optional"][0]["step_quantity"], 0)          # optional shown separately, not mandatory
        self.assertIn("KM3-7", b["purchased_and_fasteners_in_step"])     # fasteners listed, not force-matched

    def test_quantity_change_detected(self):
        x = copy.deepcopy(MINI_XCAF)
        x["instances"]["02_Rack"] = 3
        b = self.bom(x)
        self.assertEqual(b["mandatory_positions_matched"], 1)
        self.assertIn({"part_id": "02_RACK", "readme": 2, "step": 3}, b["mismatches"])

    def test_material_or_tolerance_change_detected(self):
        base = R.cad025_spec(self.bom(), "a" * 64, "b" * 64)
        changed = R.cad025_spec(self.bom(text=MINI_README.replace("Aluminum Alloy 5052", "Aluminum Alloy 6061")),
                                "a" * 64, "b" * 64)
        self.assertNotEqual(ztl_gate.spec_digest(base), ztl_gate.spec_digest(changed))
        tol = copy.deepcopy(base)
        tol["bom"][1]["dimensional_tolerances"] = "+-0.05 mm"
        self.assertNotEqual(ztl_gate.spec_digest(base), ztl_gate.spec_digest(tol))

    def test_no_values_are_invented(self):
        b = self.bom()
        finger = next(r for r in b["rows"] if r["part_id"] == "01_FINGER")
        self.assertIsNone(finger["tolerances"])                          # printed part: readme states none
        self.assertIn("dimensional_tolerances", finger["missing_requirements"])

    def test_missing_requirements_give_Z_not_T(self):
        out = R.cad025_gate(R.cad025_spec(self.bom(), "a" * 64, "b" * 64), {"verdict": "EARNED"})
        self.assertEqual(out["engineering_admission"], "Z")
        self.assertEqual(out["spec_validation"]["status"], "REFUSED")

    def test_unsigned_result_fails_cad025(self):
        # A spec complete enough to pass validation; verifier configured with a TEST key generated here (never shipped).
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
        out = R.cad025_gate(spec, {"verdict": "EARNED"}, env=env)   # stub returns attestation_jws=None
        self.assertEqual(out["spec_validation"]["status"], "VALID")
        self.assertEqual(out["admission"], "F")
        self.assertNotEqual(out["engineering_admission"], "T")

    def test_sha_substitution_blocked(self):
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

    def test_brick_values_are_sourced(self):
        brick = R.rail_length_brick(MINI_XCAF, MINI_README)
        q = brick["quantities"]
        self.assertEqual(q["L_spec"]["value"], "170")
        self.assertEqual(q["L_cad"]["range"], ["169.9995", "170.0005"])
        self.assertTrue(all(v.get("ground") for v in q.values() if v["role"] == "given"))


@unittest.skipUnless(HAVE_ZTL, "ZTL_ENGINEER_DIR not set: real stand not available")
class RealStand(unittest.TestCase):
    def test_earned_for_sourced_rail(self):
        out = R.check_design(R.rail_length_brick(MINI_XCAF, MINI_README), ZTL)
        self.assertTrue(out["stand_called"])
        self.assertEqual(out["verdict"], "EARNED")

    def test_out_of_tolerance_is_refuted(self):
        x = copy.deepcopy(MINI_XCAF)
        x["geometry"]["RAIL-170"]["bbox"] = [9.0, 6.5, 170.05]
        out = R.check_design(R.rail_length_brick(x, MINI_README), ZTL)
        self.assertEqual(out["verdict"], "REFUTED")

    def test_tightened_tolerance_changes_verdict(self):
        b = R.rail_length_brick(MINI_XCAF, MINI_README)
        b["requirements"][0]["value"] = ["-0.0001", "0.0001"]
        self.assertNotEqual(R.check_design(b, ZTL)["verdict"], "EARNED")


@unittest.skipUnless(HAVE_REAL and HAVE_OCP, "CAD027_STEP / CAD027_README / OCP not available")
class RealStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = cad_xcaf.read_assembly(STEP, R.PINNED_STEP_SHA256)

    def test_step_opens_with_xcaf_structure(self):
        self.assertEqual(self.a["verdict"], "T_XCAF_STRUCTURE")
        self.assertEqual((self.a["leaf_definitions"], self.a["leaf_instances"]), (64, 326))
        self.assertEqual(self.a["length_unit"], "mm")

    def test_bom_40_of_40_and_53_of_53(self):
        b = R.reconcile(self.a, R.parse_readme(Path(README).read_text(encoding="utf-8")), "b" * 64)
        self.assertEqual((b["mandatory_positions_matched"], b["mandatory_positions"]), (40, 40))
        self.assertEqual((b["mandatory_instances_step"], b["mandatory_instances_readme"]), (53, 53))
        self.assertEqual(b["purchased_readme_positions"], 27)
        self.assertEqual([(o["part_id"], o["quantity"], o["step_quantity"]) for o in b["optional"]],
                         [("DM_MOTOR1_WIRING_HARNESS_CLIP", 2, 0)])

    def test_rerun_reproduces(self):
        again = cad_xcaf.read_assembly(STEP, R.PINNED_STEP_SHA256)
        self.assertEqual(json.dumps(again["instances"], sort_keys=True), json.dumps(self.a["instances"], sort_keys=True))
        self.assertEqual(json.dumps(again["geometry"], sort_keys=True), json.dumps(self.a["geometry"], sort_keys=True))


if __name__ == "__main__":
    unittest.main()
