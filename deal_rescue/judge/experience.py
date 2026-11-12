"""Data for the 7-screen Judge Experience. Each screen is computed from a real source; nothing is a canned PASS.

DRAWING / PARTS / ENGINEERING REVIEW  CASE A, computed live by cad027_review (real STEP, XCAF, ZTL, CAD-025)
PROCUREMENT                            CASE A, derived from that run: what a supplier request needs, what is
                                       confirmed, and why it is blocked
COALITION                              mechanism demo on the packaged SYNTHETIC fixtures (5 x 20 -> MOQ 100),
                                       computed live by industrial.workflow
PAYMENT                                CASE B, the recorded commerce replay (run-2 dossier, 5 Sandbox captures)
RESULT                                 execution passport across both cases, with boundaries
"""
from __future__ import annotations

import json
from pathlib import Path

from deal_rescue.industrial import ztl_gate, workflow
from deal_rescue.judge import passport as P

SAMPLES = Path(__file__).resolve().parents[1] / "industrial" / "samples"
BRIDGE = [
    ("engineering_admission", "CAD-025: Ed25519-signed independent attestation covering every part and requirement"),
    ("supplier_quote", "signed supplier quote with MOQ, capacity, lead time, price and shipping"),
    ("coalition_admission", "independent admission of the coalition contract (Federation)"),
    ("buyer_commitments", "each buyer's signed commitment within its cap"),
    ("payment_permit", "operator payment permit bound to that contract; then PayPal order/capture with readback"),
]


def procurement(report: dict, part_id: str | None = None) -> dict:
    rows = (report.get("bom") or {}).get("rows") or []
    if not rows:
        return {"status": "NOT_READY", "why": "run the PARTS step first"}
    row = next((r for r in rows if r["part_id"] == part_id), None) or next(
        (r for r in rows if r["group"] == "cnc"), rows[0])
    known = {"quantity": row["quantity"], "material": row["material"], "manufacturing_process": row["manufacturing_process"],
             "dimensional_tolerances": row["tolerances"], "geometry_bbox_mm": (row.get("geometry") or {}).get("bbox")}
    fields = []
    for f in ztl_gate.PART_FIELDS:
        src = {"material": "material", "manufacturing_process": "manufacturing_process",
               "dimensional_tolerances": "dimensional_tolerances"}.get(f)
        val = known.get(src) if src else None
        fields.append({"field": f, "value": val, "status": P.T if val else P.Z,
                       "source": row["sources"]["quantity_material_process"] if val else "not stated in any source"})
    admission = (report.get("overall") or {}).get("engineering_admission") or (report.get("cad025") or {}).get(
        "engineering_admission", P.Z)
    routes = [{"route": r, "moq": "Z (no supplier quote)", "price": "Z (no supplier quote)",
               "needs": ["signed supplier quote", "ENGINEERING_ADMISSION = T"]}
              for r in ("direct purchase", "join an existing batch", "coalition with other buyers")]
    return {"case_id": P.CASE_A_ID, "part_id": row["part_id"], "group": row["group"], "quantity_per_arm": row["quantity"],
            "fields": fields, "confirmed": sum(f["status"] == P.T for f in fields), "required": len(fields),
            "engineering_admission": admission, "routes": routes,
            "status": "BLOCKED" if admission != P.T else "READY_FOR_SUPPLIER_QUOTE",
            "why": "procurement may start only after ENGINEERING_ADMISSION = T (CAD-025)",
            "rfq_draft": {"sent": False, "cad_attached": False, "to": None,
                          "text": f"Request for quotation (DRAFT, NOT SENT): {row['part_id']} x {row['quantity']} per arm, "
                                  f"material {row['material']}, process {row['manufacturing_process']}. "
                                  "Drawing released only with the owner's explicit authorization."},
            "parts": [{"part_id": r["part_id"], "group": r["group"]} for r in rows]}


def coalition() -> dict:
    claim = json.loads((SAMPLES / "DEMO-CLAIM.json").read_text(encoding="utf-8"))
    out = workflow.run_intake("BRACKET-20-ANNOTATED.dxf", (SAMPLES / "BRACKET-20-ANNOTATED.dxf").read_bytes(), claim)
    line = (out.get("lines") or [{}])[0]
    al = line.get("allocation") or {}
    return {"label": "SYNTHETIC_FIXTURE (mechanism demonstration; no real buyer, supplier quote or payment)",
            "computed_by": "deal_rescue.industrial.workflow.run_intake on samples/BRACKET-20-ANNOTATED.dxf",
            "overall": out.get("overall"), "route": line.get("best_route"), "live_execution_gate": out.get("live_execution_gate"),
            "units": al.get("units"), "moq": 100, "requests": [{"buyer": b["buyer_id"], "qty": b["qty"],
                                                                "all_in_cents": b["all_in_cents"], "budget_cents": b["budget_cents"],
                                                                "within_budget": b["within_budget"]} for b in al.get("per_buyer", [])],
            "production_cents": al.get("production_cents"), "shipping_cents": al.get("shipping_cents"),
            "total_cents": al.get("total_all_buyers_cents"), "evidence_sha256": out.get("evidence_sha256"),
            "new_paypal_captures": out.get("new_paypal_captures")}


def payment(dossier: dict) -> dict:
    pay, contract, judge = dossier["paypal"], dossier["contract"], dossier["judge"]
    slots = [{k: s.get(k) for k in ("customer", "owner_id", "amount_cents", "state", "order_id", "capture_id",
                                     "contract_hash", "mission_id", "status_source")} for s in pay["slots"]]
    bound = P.bind_payments(slots[0]["contract_hash"], pay["slots"])          # all five on one contract, or error
    terms = [{"version": t.get("version"), "design": t.get("design"), "per_buyer_cents": t.get("per_buyer_cents"),
              "total_cents": t.get("total_cents"), "final_state": t.get("final_state"),
              "why": (t.get("failure") or {}).get("reason")} for t in dossier.get("terms_versions", [])]
    return {"case_id": P.CASE_B_ID, "label": "RECORDED Sandbox replay (PayPal Sandbox, no real money)",
            "requests": [{"customer": r["customer"], "units": r["units"], "max_cents": r["max_cents"],
                          "alone": r["refusal_reason"]} for r in dossier["requests"]],
            "moq": contract.get("supplier_moq"), "terms_versions": terms,
            "judge": {"verdict": judge["verdict"], "checks": f"{judge['checks_passed']}/{judge['checks_total']}",
                      "scope": judge["scope"]},
            "contract_hash": bound["contract_hash"], "captures": slots,
            "readback_confirmed_captures": pay["readback_confirmed_captures"],
            "provider_confirmed_cents": pay["provider_confirmed_cents"], "badge": pay["badge"]}


def bridge(case_a_admission: str) -> list:
    out, open_from = [], None
    for i, (gate, what) in enumerate(BRIDGE):
        status = case_a_admission if i == 0 else P.Z
        if status != P.T and open_from is None:
            open_from = gate
        out.append({"gate": gate, "requires": what, "case_a_status": status})
    return out


def result(report: dict, coal: dict, pay: dict, judge_go: dict | None) -> dict:
    o = report.get("overall") or {}
    a_hash = P.case_a_contract_hash(report["drawing"]["sha256"], P.canonical_hash(report["bom"]["rows"]),
                                    report["ztl"]["requirements_digest"]) if report.get("ztl") else None
    try:
        P.bind_payments(a_hash, pay["captures"])
        cross = "ATTRIBUTED"            # never expected
    except P.BindingError as e:
        cross = f"REFUSED: {e}"
    return {"case_a": {"id": P.CASE_A_ID, "contract_hash": a_hash, "cad_sha256": report["drawing"]["sha256"],
                       "ocp": o.get("ocp_xcaf"), "bom": o.get("bom"), "ztl_production": o.get("ztl_production"),
                       "rail_tolerance": o.get("rail_tolerance"), "engineering_admission": o.get("engineering_admission"),
                       "procurement": "BLOCKED" if o.get("engineering_admission") != P.T else "READY",
                       "payments": 0},
            "coalition_mechanism": {"label": coal["label"], "units": coal["units"], "total_cents": coal["total_cents"]},
            "case_b": {"id": P.CASE_B_ID, "contract_hash": pay["contract_hash"], "captures": len(pay["captures"]),
                       "provider_confirmed_cents": pay["provider_confirmed_cents"], "judge": pay["judge"]},
            "cross_case_payment_attribution": cross,
            "bridge": bridge(o.get("engineering_admission", P.Z)),
            "boundaries": {"real": "reBot STEP, XCAF, BOM, ZTL stand calls, CAD-025 gate (computed on this machine)",
                           "recorded": "CASE B commerce run and its five PayPal Sandbox captures (Sandbox, no real money)",
                           "synthetic": "coalition fixture buyers and prices",
                           "not_executed": "new PayPal capture, supplier request, CAD transmission"},
            "judge_go_no_go": judge_go}
