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
CNC_TOLERANCE = "+-0.02 mm key dimensions (GB/T1804-M); mating parts H7 / interference fit"
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
def rail_length_brick(xcaf: dict, readme_text: str) -> dict:
    """Predicate with every value sourced: modelled MGN9 rail length vs the readme purchase spec, within the
    readme key-dimension tolerance. The STEP value is the XCAF bounding-box extent rounded to 0.001 mm, so it is
    given as a +-0.0005 mm range (no other uncertainty claimed)."""
    m = re.search(r"\|\s*Linear rail\s*\|\s*MGN9-(\d+)mm\s*\|", readme_text)
    if not m:
        raise ValueError("RAIL_SPEC_NOT_IN_README")
    geo = xcaf["geometry"].get("RAIL-170")
    if not geo or not geo.get("bbox"):
        raise ValueError("RAIL_NOT_IN_STEP")
    from decimal import Decimal
    length = Decimal(f"{max(geo['bbox']):.3f}")
    half = Decimal("0.0005")
    lo, hi = str(length - half), str(length + half)
    return {
        "stand": "ztl-stand/1",
        "quantities": {
            "L_cad": {"role": "given", "range": [lo, hi], "unit": "mm",
                      "ground": f"STEP XCAF bbox of RAIL-170 in {xcaf['file']} sha256 {xcaf['sha256'][:16]}"},
            "L_spec": {"role": "given", "value": m.group(1), "unit": "mm",
                       "ground": "readme.md purchased parts: Linear rail MGN9-" + m.group(1) + "mm"},
            "dL": {"role": "derived", "unit": "mm"}},
        "slots": {}, "catalog": {},
        "laws": [{"zfl": "dL == L_cad - L_spec", "source": "deviation of the modelled rail length from the purchase spec"}],
        "requirements": [{"quantity": "dL", "op": "within", "value": ["-0.02", "0.02"],
                          "why": "readme.md Machining Specifications: key dimension tolerance +-0.02 mm"}],
    }


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
        return {"verdict": "OPEN", "stand_called": True, "why": "NO_MCP_REPLY", "stderr": p.stderr[-800:]}
    text = reply["result"]["content"][0]["text"]
    try:
        out = json.loads(text)
    except ValueError:
        out = {"verdict": "STAND ERROR", "why": text[:800]}
    out["stand_called"] = True
    out["seconds"] = round(time.time() - t0, 2)
    out["via"] = "ztl-engineer/mcp_server.py tools/call check_design -> python -m ustand.stand"
    return out


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
def run(step_path, readme_path, ztl_engineer_dir=None, expected_sha256=PINNED_STEP_SHA256, stages=4) -> dict:
    step_path, readme_path = Path(step_path), Path(readme_path)
    started = datetime.now(timezone.utc).isoformat()
    readme_bytes = readme_path.read_bytes()
    readme_sha = hashlib.sha256(readme_bytes).hexdigest()
    readme_text = readme_bytes.decode("utf-8")
    report = {"schema": "legion.cad027.demo.v1", "run_utc": started,
              "drawing": {"file": step_path.name, "bytes": step_path.stat().st_size,
                          "expected_sha256": expected_sha256, "readme": readme_path.name, "readme_sha256": readme_sha}}
    try:
        xcaf = cad_xcaf.read_assembly(step_path, expected_sha256)
    except cad_xcaf.SourceMismatch as e:
        report["drawing"].update(status=F, error=str(e))
        report["overall"] = {"demo": F, "engineering_admission": Z, "blocked_at": "drawing"}
        return report
    report["drawing"].update(status=T, sha256=xcaf["sha256"])
    report["xcaf"] = xcaf
    if stages < 2:
        return report
    bom = reconcile(xcaf, parse_readme(readme_text), readme_sha)
    report["bom"] = bom
    bom_ok = bom["mandatory_positions_matched"] == bom["mandatory_positions"] and \
        bom["mandatory_instances_step"] == bom["mandatory_instances_readme"]
    report["bom_status"] = T if bom_ok else F
    if stages < 3:
        return report
    brick = rail_length_brick(xcaf, readme_text)
    ztl = check_design(brick, ztl_engineer_dir)
    report["ztl"] = {"brick": brick, "result": ztl, "verdict": ztl.get("verdict"),
                     "guaranteed": ztl.get("guaranteed"), "judge": ztl.get("judge"),
                     "scope": "ONE predicate: modelled MGN9 rail length vs readme spec within +-0.02 mm. "
                              "EARNED here does not approve any part or the assembly."}
    spec = cad025_spec(bom, xcaf["sha256"], readme_sha)
    report["cad025"] = cad025_gate(spec, unsigned_ztl_result=ztl)
    report["overall"] = {
        "demo": T if bom_ok and ztl.get("stand_called") and ztl.get("verdict") in ("EARNED", "REFUTED", "OPEN") else F,
        "ocp_xcaf": T, "bom": report["bom_status"], "ztl_predicate": ztl.get("verdict"),
        "engineering_admission": report["cad025"]["engineering_admission"],
        "missing_for_engineering_T": ["per-part dimensional requirements and tolerances for printed parts",
                                      "material grade certificates", "surface finish per part",
                                      "inspection requirements", "functional requirements",
                                      "independent Ed25519 attestation (CAD-025)"],
        "external_effects": {"supplier_requests": 0, "paypal_calls": 0, "cad_transmitted": 0}}
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    return report


def mutate_quantity(bom_xcaf: dict, part: str, delta: int) -> dict:
    x = copy.deepcopy(bom_xcaf)
    x["instances"][part] += delta
    return x


class StagedRun:
    """One demo run, advanced one stage at a time by the UI. Each stage uses the previous stage's real output."""

    def __init__(self, step_path, readme_path, ztl_engineer_dir):
        self.step_path, self.readme_path, self.ztl_dir = Path(step_path), Path(readme_path), ztl_engineer_dir
        self.report = None

    def configured(self):
        return self.step_path.is_file() and self.readme_path.is_file()

    def stage(self, n: int) -> dict:
        if n == 1 or self.report is None:
            rb = self.readme_path.read_bytes()
            self.report = {"schema": "legion.cad027.demo.v1", "run_utc": datetime.now(timezone.utc).isoformat(),
                           "stage": 0, "drawing": {"file": self.step_path.name, "bytes": self.step_path.stat().st_size,
                                                   "expected_sha256": PINNED_STEP_SHA256,
                                                   "sha256": cad_xcaf.sha256_file(self.step_path),
                                                   "readme": "hardware/reBot_B601_DM/readme.md",
                                                   "readme_sha256": hashlib.sha256(rb).hexdigest()}}
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
            b = r["bom"]
            r["bom_status"] = T if (b["mandatory_positions_matched"] == b["mandatory_positions"] and
                                    b["mandatory_instances_step"] == b["mandatory_instances_readme"]) else F
            r["stage"] = 2
        if n >= 3 and r["stage"] < 3:
            brick = rail_length_brick(r["xcaf"], self.readme_path.read_text(encoding="utf-8"))
            ztl = check_design(brick, self.ztl_dir)
            r["ztl"] = {"brick": brick, "result": ztl, "verdict": ztl.get("verdict"), "guaranteed": ztl.get("guaranteed"),
                        "judge": ztl.get("judge"),
                        "scope": "ONE predicate: modelled MGN9 rail length vs readme spec within +-0.02 mm. "
                                 "EARNED here does not approve any part or the assembly."}
            r["cad025"] = cad025_gate(cad025_spec(r["bom"], r["drawing"]["sha256"], r["drawing"]["readme_sha256"]), ztl)
            r["stage"] = 3
        if n >= 4 and r["stage"] < 4:
            ztl = r["ztl"]["result"]
            r["overall"] = {
                "demo": T if r["bom_status"] == T and ztl.get("stand_called") and
                ztl.get("verdict") in ("EARNED", "REFUTED", "OPEN") else F,
                "ocp_xcaf": T, "bom": r["bom_status"], "ztl_predicate": ztl.get("verdict"),
                "engineering_admission": r["cad025"]["engineering_admission"],
                "missing_for_engineering_T": ["per-part dimensional requirements and tolerances for printed parts",
                                              "material grade certificates", "surface finish per part",
                                              "inspection requirements", "functional requirements",
                                              "independent Ed25519 attestation (CAD-025)"],
                "external_effects": {"supplier_requests": 0, "paypal_calls": 0, "cad_transmitted": 0}}
            r["finished_utc"] = datetime.now(timezone.utc).isoformat()
            r["stage"] = 4
        return r
