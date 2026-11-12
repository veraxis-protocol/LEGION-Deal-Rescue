"""CAD-027 demo: one real STEP -> XCAF parts -> BOM reconciled with the factory README -> real ZTL Engineer check
-> CAD-025 engineering gate. Every value carries its source; nothing is inferred.

Stages (each one runs only on the previous stage's real output):
  1 drawing      pinned STEP file (SHA-256 checked) + factory readme
  2 parts        OpenCascade XCAF tree (cad_xcaf) reconciled with the readme BOM tables
  3 engineering  a ZTL brick built from sourced values, judged by the real ZTL stand through
                 ztl-engineer/mcp_server.py tool ``check_design`` (python -m ustand.stand); then the CAD-025 gate
  4 result       one JSON report
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from deal_rescue.industrial import cad_xcaf, ztl_gate

T, F, Z = "T", "F", "Z"
PINNED_STEP_SHA256 = "a1e301ee03d46589e26d3fc2272d19ba53c1878f0104274695e5c9a88aa512d2"
PINNED_STEP_NAME = "reBot_B601_DM_v1.1_20260625.step"
CNC_TOLERANCE = "±0.02 mm key dimensions, GB/T1840-M (readme Machining Specifications); mating parts H7 / interference fit"
STAND_TIME_LIMIT_S = 120


def _norm(name: str) -> str:
    n = re.sub(r"\.(step|stp)$", "", name.strip().strip("`").strip(), flags=re.I)
    return n.replace("-", "_").replace(" ", "_").upper()


def _rows(lines, start):
    """Markdown table rows from line index ``start`` (header), until the table ends."""
    out, header = [], None
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if not s.startswith("|"):
            if header is not None:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        out.append((i + 1, dict(zip(header, cells))))
    return out


def parse_readme(text: str) -> dict:
    """Factory BOM tables of the reBot B601 DM readme, with source line numbers."""
    lines = text.splitlines()

    def table_after(marker, nth=0):
        hits = [i for i, l in enumerate(lines) if marker in l]
        return _rows(lines, hits[nth] + 1) if len(hits) > nth else []

    printed, cnc, optional, purchased = [], [], [], []
    for line, r in table_after("## 🖨️ 3D Printed Parts"):
        if r.get("File Name", "").lower().endswith((".step", ".stp")):
            printed.append({"part_id": _norm(r["File Name"]), "file": r["File Name"], "readme_line": line,
                            "quantity": int(r["Qty"]), "material": r["Material"],
                            "manufacturing_process": "FDM 3D printing (" + r["Notes"] + ")",
                            "tolerances": None, "group": "printed"})
    clip_hdr = next(i for i, l in enumerate(lines) if "Wiring Harness Clips" in l) - 2
    for line, r in _rows(lines, clip_hdr):
        optional.append({"part_id": _norm(r["File Name"]), "file": r["File Name"].strip("`"), "readme_line": line,
                         "quantity": int(r["Qty"]), "material": r["Material"],
                         "manufacturing_process": "FDM 3D printing (" + r["Remarks"] + ")",
                         "tolerances": None, "group": "optional"})
    for line, r in table_after("## 🔩 CNC Machined Metal Parts"):
        if r.get("File Name", "").lower().endswith(".step"):
            cnc.append({"part_id": _norm(r["File Name"]), "file": r["File Name"], "readme_line": line,
                        "quantity": int(r["Qty"]), "material": r["Material"],
                        "manufacturing_process": r["Machining"], "tolerances": CNC_TOLERANCE, "group": "cnc"})
    for line, r in table_after("## 🛒 Purchased Parts"):
        if r.get("Quantity") is not None:
            purchased.append({"name": r.get("Name", ""), "model": r.get("Specification / Model", ""),
                              "quantity_text": r["Quantity"], "readme_line": line})
    return {"printed": printed, "cnc": cnc, "optional": optional, "purchased": purchased}


def reconcile(xcaf: dict, readme: dict, readme_sha256: str) -> dict:
    """Readme fabricated parts vs XCAF instance counts. Mismatches are listed, never corrected."""
    observed = {_norm(k): (k, v) for k, v in xcaf["instances"].items()}
    used, rows = set(), []
    for item in readme["printed"] + readme["cnc"] + readme["optional"]:
        name, qty = observed.get(item["part_id"], (None, 0))
        if name:
            used.add(name)
        geo = xcaf["geometry"].get(name) if name else None
        missing = [f for f, v in (("dimensional_tolerances", item["tolerances"]),) if not v]
        missing += ["material_grade_certificate", "surface_finish_per_part", "inspection_requirements",
                    "functional_requirements"]
        rows.append({**item, "step_name": name, "step_quantity": qty,
                     "quantity_match": qty == item["quantity"],
                     "geometry": None if geo is None else {**geo, "unit": xcaf["length_unit"]},
                     "sources": {"quantity_material_process": f"readme.md line {item['readme_line']} sha256 {readme_sha256}",
                                 "step_quantity_geometry": f"{xcaf['file']} XCAF sha256 {xcaf['sha256']}"},
                     "missing_requirements": missing})
    mandatory = [r for r in rows if r["group"] != "optional"]
    purchased_known = {_norm(p["model"]) for p in readme["purchased"]}
    unmatched_step = {k: v for k, v in xcaf["instances"].items() if k not in used}
    return {
        "schema": "legion.cad027.bom.v1",
        "mandatory_positions": len(mandatory),
        "mandatory_positions_matched": sum(r["quantity_match"] for r in mandatory),
        "mandatory_instances_readme": sum(r["quantity"] for r in mandatory),
        "mandatory_instances_step": sum(r["step_quantity"] for r in mandatory),
        "optional": [r for r in rows if r["group"] == "optional"],
        "rows": mandatory,
        "mismatches": [{"part_id": r["part_id"], "readme": r["quantity"], "step": r["step_quantity"]}
                       for r in rows if not r["quantity_match"]],
        "purchased_readme": readme["purchased"],
        "purchased_readme_positions": len(readme["purchased"]),
        "purchased_and_fasteners_in_step": dict(sorted(unmatched_step.items())),
        "purchased_exact_code_matches": sorted(k for k in unmatched_step if _norm(k) in purchased_known),
        "note": "Purchased rows use model names (e.g. DM4310) that differ from STEP product names (DM-J4310); "
                "they are listed side by side, not force-matched. Readme fastener counts are minimums ('14+').",
    }


# ---------------------------------------------------------------- ZTL Engineer (real stand)
# Provenance rule (WO-CAD027-REVIEW-CLOSURE-002): a predicate goes to the stand only when EVERY input and the
# requirement itself come from a source that states them for THIS part. STEP geometry is a nominal model: its
# 0.001 mm rounding is representation precision, never manufacturing precision.

class ToleranceUnsupported(ValueError):
    """No source states a tolerance that applies to this part."""


def _line_of(text: str, needle: str):
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i, line.strip()
    return None, None


def tolerance_for_purchased_rail(readme_text: str) -> dict:
    """The readme's only tolerance sits under 'CNC Machined Metal Parts / Machining Specifications'. It applies to
    machined parts, not to the purchased MGN9 rail. No other source states a rail tolerance -> Z."""
    tol_line, tol_text = _line_of(readme_text, "Key dimension tolerance")
    rail_line, rail_text = _line_of(readme_text, "MGN9-170mm")
    cnc_line, _ = _line_of(readme_text, "## 🔩 CNC Machined Metal Parts")
    bought_line, _ = _line_of(readme_text, "## 🛒 Purchased Parts")
    return {"part": "MGN9-170mm linear rail (purchased)", "verdict": Z,
            "rail_source": {"document": "hardware/reBot_B601_DM/readme.md", "line": rail_line, "text": rail_text},
            "only_tolerance_in_sources": {"document": "hardware/reBot_B601_DM/readme.md", "line": tol_line,
                                          "text": tol_text, "section": f"CNC Machined Metal Parts (line {cnc_line})",
                                          "applies_to": "CNC machined metal parts",
                                          "applies_to_purchased_rail": False,
                                          "why": f"the rail is listed under Purchased Parts (line {bought_line}), "
                                                 "outside the section the tolerance belongs to"},
            "missing": ["manufacturer length tolerance for MGN9-170 rail (datasheet)"]}


def rail_length_brick(xcaf: dict, readme_text: str, tolerance_mm: tuple | None = None,
                      tolerance_source: str | None = None) -> dict:
    """Rail length check. Without an explicitly sourced tolerance it raises ToleranceUnsupported (verdict Z).
    The STEP length is the nominal model value, given exactly: no manufacturing spread is claimed from it."""
    m = re.search(r"\|\s*Linear rail\s*\|\s*MGN9-(\d+)mm\s*\|", readme_text)
    if not m:
        raise ValueError("RAIL_SPEC_NOT_IN_README")
    if tolerance_mm is None or not tolerance_source:
        raise ToleranceUnsupported("RAIL_TOLERANCE=Z: no source states a tolerance for the purchased MGN9 rail")
    geo = xcaf["geometry"].get("RAIL-170")
    if not geo or not geo.get("bbox"):
        raise ValueError("RAIL_NOT_IN_STEP")
    from decimal import Decimal
    length = str(Decimal(f"{max(geo['bbox']):.3f}"))
    return {
        "stand": "ztl-stand/1",
        "quantities": {
            "L_cad": {"role": "given", "value": length, "unit": "mm",
                      "ground": f"STEP nominal model, XCAF bbox of RAIL-170 in {xcaf['file']}"},
            "L_spec": {"role": "given", "value": m.group(1), "unit": "mm",
                       "ground": "readme.md purchased parts: Linear rail MGN9-" + m.group(1) + "mm"},
            "dL": {"role": "derived", "unit": "mm"}},
        "slots": {}, "catalog": {},
        "laws": [{"zfl": "dL == L_cad - L_spec", "source": "deviation of the modelled rail length from the purchase spec"}],
        "requirements": [{"quantity": "dL", "op": "within", "value": [str(tolerance_mm[0]), str(tolerance_mm[1])],
                          "why": tolerance_source}],
    }


def production_predicates(xcaf: dict, readme_text: str, perf_text: str | None) -> list:
    """Candidate reBot engineering predicates and whether the sources allow a stand check. None is invented."""
    preds = []
    rail = tolerance_for_purchased_rail(readme_text)
    preds.append({"id": "rail_length_tolerance", "verdict": "OPEN", "stand_called": False,
                  "requirement": "MGN9-170 rail length within its manufacturing tolerance",
                  "inputs": {"L_spec": {"value": "170 mm", "source": f"readme.md line {rail['rail_source']['line']}"},
                             "L_cad": {"value": f"{max(xcaf['geometry'].get('RAIL-170', {}).get('bbox') or [0]):.3f} mm",
                                       "source": "STEP XCAF bbox (nominal model; 0.001 mm is representation rounding, "
                                                 "not manufacturing precision)"}},
                  "tolerance": rail, "RAIL_TOLERANCE": Z,
                  "missing": rail["missing"]})
    load = {"id": "joint2_load_torque", "verdict": "OPEN", "stand_called": False,
            "requirement": "joint 2 holding torque at the recommended load stays within its motor rating"}
    if perf_text:
        l_line, l_text = _line_of(perf_text, "- Load: < 1.5 kg")
        r_line, r_text = _line_of(perf_text, "Working radius: < 70% reach (450 mm)")
        c_line, c_text = _line_of(perf_text, "12Nm Load Curve</p>")
        load["inputs"] = {
            "payload": {"value": "< 1.5 kg", "source": f"Performance_Testing.md line {l_line}: {l_text}"},
            "radius": {"value": "< 450 mm", "source": f"Performance_Testing.md line {r_line}: {r_text}"},
            "motor_curve": {"value": "12 Nm load curve (Damiao 43 series)", "source": f"Performance_Testing.md line {c_line}"}}
        load["missing"] = ["arm self-weight and centre of mass (no masses or densities in the sources)",
                           "which motor is joint 2 and its rated (continuous) torque, as opposed to the curve title",
                           "joint-2 axis position relative to the payload in the reference posture"]
    else:
        load["missing"] = ["Performance_Testing.md not supplied"]
    preds.append(load)
    return preds


def integration_test_scenario(ztl_engineer_dir: str | None) -> dict:
    """SEPARATELY LABELLED TEST: proves the real stand is reachable and answers, using ztl-stand's own shipped
    example brick (a resistor divider). It is NOT a reBot check and approves nothing about the arm."""
    root = Path(ztl_engineer_dir or os.environ.get("ZTL_ENGINEER_DIR", "")).resolve()
    example = Path(os.environ.get("ZTL_ENGINEER_STAND", root.parent / "ztl-stand")) / "examples" / "divider-1pct-req-1pct.json"
    if not example.is_file():
        return {"label": "TEST_SCENARIO_NOT_REBOT", "verdict": "OPEN", "stand_called": False, "why": f"missing {example}"}
    brick = json.loads(example.read_text(encoding="utf-8"))
    out = check_design(brick, ztl_engineer_dir)
    return {"label": "TEST_SCENARIO_NOT_REBOT", "brick_source": "ztl-stand examples/divider-1pct-req-1pct.json",
            "brick_sha256": hashlib.sha256(example.read_bytes()).hexdigest(),
            "verdict": out.get("verdict"), "judge": out.get("judge"), "stand_called": out.get("stand_called"),
            "seconds": out.get("seconds"), "via": out.get("via"),
            "scope": "integration health of the ZTL route only; says nothing about the reBot arm"}


def requirements_digest(preds: list) -> str:
    """Fingerprint of the sourced requirements and inputs: any change in a source line changes it."""
    keep = [{k: p.get(k) for k in ("id", "requirement", "inputs", "missing")} for p in preds]
    return hashlib.sha256(json.dumps(keep, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def check_design(brick: dict, ztl_engineer_dir: str | None = None, time_limit_s: int = STAND_TIME_LIMIT_S) -> dict:
    """Call the real ztl-engineer MCP server (stdio JSON-RPC) tool check_design. No local pass/fail."""
    root = Path(ztl_engineer_dir or os.environ.get("ZTL_ENGINEER_DIR", "")).resolve()
    server = root / "mcp_server.py"
    if not server.is_file():
        return {"verdict": "OPEN", "stand_called": False, "why": f"ZTL_ENGINEER_NOT_FOUND: {server}"}
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "check_design", "arguments": {"brick": brick, "time_limit_s": time_limit_s}}}]
    t0 = time.time()
    # UTF-8 both ways: on Windows the locale code page cannot decode the stand's output, and subprocess then
    # silently leaves stdout as None.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.run([sys.executable, str(server)], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                       capture_output=True, encoding="utf-8", errors="replace", env=env, timeout=time_limit_s + 60)
    reply = next((json.loads(l) for l in (p.stdout or "").splitlines()
                  if l.strip().startswith("{") and json.loads(l).get("id") == 1), None)
    if not reply or "result" not in reply:
        return {"verdict": "OPEN", "stand_called": True, "why": "NO_MCP_REPLY", "stderr": (p.stderr or "")[-800:]}
    text = reply["result"]["content"][0]["text"]
    try:
        out = json.loads(text)
    except ValueError:
        out = {"verdict": "STAND ERROR", "why": text[:800]}
    out["stand_called"] = True
    out["seconds"] = round(time.time() - t0, 2)
    out["via"] = "ztl-engineer/mcp_server.py tools/call check_design -> python -m ustand.stand"
    return out


def ztl_review(xcaf: dict, readme_text: str, perf_text: str | None, ztl_engineer_dir: str | None) -> dict:
    preds = production_predicates(xcaf, readme_text, perf_text)
    decided = [p for p in preds if p["verdict"] in ("EARNED", "REFUTED")]
    return {"production_verdict": "OPEN" if not decided else ("REFUTED" if any(p["verdict"] == "REFUTED" for p in decided) else "EARNED"),
            "production_scope": "reBot predicates whose inputs AND requirement are stated by the sources; none is "
                                "complete, so the stand is not called on invented values",
            "predicates": preds, "requirements_digest": requirements_digest(preds),
            "integration_test": integration_test_scenario(ztl_engineer_dir)}

# ---------------------------------------------------------------- CAD-025 linkage
def cad025_spec(bom: dict, step_sha: str, readme_sha: str) -> dict:
    """The CAD-025 spec as far as the sources allow. Absent fields stay absent: the gate must refuse."""
    parts, reqs = [], []
    for r in bom["rows"]:
        part = {"part_number": r["part_id"][:80], "quantity": r["quantity"], "material": r["material"],
                "manufacturing_process": r["manufacturing_process"], "source_sha256": readme_sha}
        if r["tolerances"]:
            part["dimensional_tolerances"] = r["tolerances"]
        parts.append(part)
        reqs.append({"id": f"{r['part_id'][:60]}.material", "part_number": r["part_id"][:80], "category": "material",
                     "statement": r["material"], "source_sha256": readme_sha})
    return {"drawing_sha256": step_sha, "drawing_revision": "v1.1_20260625",
            "source_documents": [{"document_id": PINNED_STEP_NAME, "kind": "step", "sha256": step_sha},
                                 {"document_id": "hardware/reBot_B601_DM/readme.md", "kind": "bom", "sha256": readme_sha}],
            "bom": parts, "requirements": reqs}


def cad025_gate(spec: dict, unsigned_ztl_result: dict | None = None, env: dict | None = None) -> dict:
    """Run the installed CAD-025 gate. An unsigned ZTL result is never accepted as authority."""
    out = {"gate": "deal_rescue.industrial.ztl_gate (CAD-025)"}
    try:
        out["spec_validation"] = {"status": "VALID", **{k: v for k, v in ztl_gate.validate_spec(spec).items() if k != "sources"}}
    except ztl_gate.GateError as e:
        out["spec_validation"] = {"status": "REFUSED", "code": e.code}
    try:
        ztl_gate.engineering_admission("CAD027DEMO001", spec, env=env or {},
                                       http_post=(lambda *a: {"attestation_jws": None, "ztl": unsigned_ztl_result}))
        out["admission"] = T
    except ztl_gate.GateError as e:
        out["admission"] = Z if e.code in ("TRUSTED_ZTL_SERVICE_NOT_CONFIGURED",) else F
        out["admission_code"] = e.code
    out["engineering_admission"] = T if out["admission"] == T else Z
    out["why"] = "CAD-025 grants engineering T only for an Ed25519-signed attestation from the configured independent " \
                 "verifier covering every part and requirement; none exists here."
    return out


# ---------------------------------------------------------------- pipeline
MISSING_FOR_ENGINEERING_T = ["per-part dimensional requirements and tolerances for printed parts",
                             "manufacturer tolerance for the purchased MGN9-170 rail",
                             "material grade certificates", "surface finish per part",
                             "inspection requirements", "functional requirements",
                             "independent Ed25519 attestation (CAD-025)"]


def bom_status(bom: dict) -> str:
    return T if (bom["mandatory_positions_matched"] == bom["mandatory_positions"] and
                 bom["mandatory_instances_step"] == bom["mandatory_instances_readme"]) else F


def demo_status(r: dict) -> str:
    """DEMO_GO = the software route works on the real file with correctly scoped results. It is NOT engineering
    admission (that is CAD-025's T, which needs a signed independent attestation)."""
    z = r.get("ztl", {})
    ok = (r["drawing"]["status"] == T and r.get("bom_status") == T
          and z.get("production_verdict") in ("EARNED", "REFUTED", "OPEN")
          and z.get("integration_test", {}).get("stand_called") is True
          and all(p["verdict"] != "EARNED" or p.get("stand_called") for p in z.get("predicates", []))
          and r.get("cad025", {}).get("engineering_admission") in (Z, T))
    return T if ok else F


def run(step_path, readme_path, ztl_engineer_dir=None, perf_path=None) -> dict:
    """Whole pipeline in one call (tests, CLI). Same code path as the UI's staged run."""
    return StagedRun(step_path, readme_path, ztl_engineer_dir, perf_path).stage(4)


def mutate_quantity(bom_xcaf: dict, part: str, delta: int) -> dict:
    x = copy.deepcopy(bom_xcaf)
    x["instances"][part] += delta
    return x


class StagedRun:
    """One demo run, advanced one stage at a time by the UI. Each stage uses the previous stage's real output."""

    def __init__(self, step_path, readme_path, ztl_engineer_dir, perf_path=None):
        self.step_path, self.readme_path, self.ztl_dir = Path(step_path), Path(readme_path), ztl_engineer_dir
        self.perf_path = Path(perf_path) if perf_path else None
        self.report = None

    def configured(self):
        return self.step_path.is_file() and self.readme_path.is_file()

    def _perf_text(self):
        return self.perf_path.read_text(encoding="utf-8") if self.perf_path and self.perf_path.is_file() else None

    def stage(self, n: int) -> dict:
        if n == 1 or self.report is None:
            rb = self.readme_path.read_bytes()
            docs = {"readme": {"path": "hardware/reBot_B601_DM/readme.md", "sha256": hashlib.sha256(rb).hexdigest()}}
            if self.perf_path and self.perf_path.is_file():
                docs["performance_testing"] = {"path": "hardware/reBot_B601_DM/performance_testing/Performance_Testing.md",
                                               "sha256": cad_xcaf.sha256_file(self.perf_path)}
            self.report = {"schema": "legion.cad027.demo.v2", "run_utc": datetime.now(timezone.utc).isoformat(),
                           "stage": 0, "source_documents": docs,
                           "drawing": {"file": self.step_path.name, "bytes": self.step_path.stat().st_size,
                                       "expected_sha256": PINNED_STEP_SHA256,
                                       "sha256": cad_xcaf.sha256_file(self.step_path),
                                       "readme": docs["readme"]["path"], "readme_sha256": docs["readme"]["sha256"]}}
            d = self.report["drawing"]
            d["status"] = T if d["sha256"] == PINNED_STEP_SHA256 else F
            self.report["stage"] = 1
        r = self.report
        if r["drawing"]["status"] != T:
            r["overall"] = {"demo": F, "engineering_admission": Z, "blocked_at": "drawing", "why": "SHA256_MISMATCH"}
            return r
        if n >= 2 and r["stage"] < 2:
            xcaf = cad_xcaf.read_assembly(self.step_path, PINNED_STEP_SHA256)
            r["xcaf"] = xcaf
            r["bom"] = reconcile(xcaf, parse_readme(self.readme_path.read_text(encoding="utf-8")),
                                 r["drawing"]["readme_sha256"])
            r["bom_status"] = bom_status(r["bom"])
            r["stage"] = 2
        if n >= 3 and r["stage"] < 3:
            r["ztl"] = ztl_review(r["xcaf"], self.readme_path.read_text(encoding="utf-8"), self._perf_text(), self.ztl_dir)
            r["cad025"] = cad025_gate(cad025_spec(r["bom"], r["drawing"]["sha256"], r["drawing"]["readme_sha256"]),
                                      r["ztl"])
            r["stage"] = 3
        if n >= 4 and r["stage"] < 4:
            r["overall"] = {
                "demo": demo_status(r), "demo_means": "software route works on the real file; NOT engineering admission",
                "ocp_xcaf": T, "bom": r["bom_status"],
                "ztl_production": r["ztl"]["production_verdict"],
                "rail_tolerance": Z,
                "ztl_integration_test": r["ztl"]["integration_test"].get("verdict"),
                "engineering_admission": r["cad025"]["engineering_admission"],
                "missing_for_engineering_T": MISSING_FOR_ENGINEERING_T,
                "external_effects": {"supplier_requests": 0, "paypal_calls": 0, "cad_transmitted": 0}}
            r["finished_utc"] = datetime.now(timezone.utc).isoformat()
            r["stage"] = 4
        return r


SETUP_ACTION = "Run `python -m scripts.judge_demo` from a clone: it fetches the pinned STEP, readme and ZTL and starts " \
               "the server configured (or start the server with --cad027-step/--cad027-readme/--cad027-perf/--ztl-engineer)."


def cad_status(run: "StagedRun | None") -> dict:
    """Why CAD is or is not usable, with the action that fixes it. Never an unexplained error."""
    if run is None:
        return {"configured": False, "reason": "CAD_NOT_CONFIGURED: server started without --cad027-step",
                "action": SETUP_ACTION}
    missing = [n for n, p in (("STEP", run.step_path), ("readme", run.readme_path)) if not p.is_file()]
    if missing:
        return {"configured": False, "reason": "CAD_INPUT_MISSING: " + ", ".join(missing), "action": SETUP_ACTION,
                "file": run.step_path.name}
    ztl_ok = bool(run.ztl_dir) and (Path(run.ztl_dir) / "mcp_server.py").is_file()
    return {"configured": True, "file": run.step_path.name, "ztl_available": ztl_ok,
            "perf_available": bool(run.perf_path and run.perf_path.is_file()),
            "note": None if ztl_ok else "ZTL Engineer not found: the review will show the stand as not called (OPEN)"}
