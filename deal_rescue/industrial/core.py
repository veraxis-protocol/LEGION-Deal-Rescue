"""LEGION Industrial: read-only sourcing + demand matching + proposal gate.

A source listing is not a quote; an opted-in demo identity is not a real buyer;
a ZTL theorem for a supported model is not a certificate of physical manufacture.
No network, accounts, payments, mutations or model calls are performed here.
Python 3.11+ standard library only. All money in exact integer US cents.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

T, F, Z = "T", "F", "Z"
DATA = Path(__file__).parent / "data"


def digest(obj):
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_json(name):
    if not name.endswith(".json") or "/" in name or "\\" in name:
        raise ValueError("untrusted data name")
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def source_registry():
    records = read_json("sources.json")["records"]
    seen = set()
    for r in records:
        if r["id"] in seen or not r["official_source"].startswith("https://"):
            raise ValueError("duplicate or invalid source")
        seen.add(r["id"])
    return {
        "total": len(records),
        "by_type": dict(sorted(Counter(r["type"] for r in records).items())),
        "coverage": "DISCOVERY_SEED_ONLY_GLOBAL_COMPLETENESS_Z",
        "records": [
            {"id": r["id"], "name": r["name"], "kind": r["type"],
             "url": r["official_source"], "capability_claim": r["observed_capability"],
             "quote_verdict": Z, "capacity_verdict": Z, "api_access_verdict": Z,
             "supplier_commitment_verdict": Z}
            for r in records
        ],
    }


def valid_demand(d, *, demonstration=False):
    """Returns screening truth, never cryptographic owner authorization."""
    keys = ("id", "buyer_id", "spec_digest", "spec_revision", "process", "material",
            "qty", "budget_cents", "due_date", "consent_scope")
    missing = [k for k in keys if k not in d or d[k] in (None, "")]
    if missing:
        return {"verdict": Z, "why": "missing_fields", "fields": missing}
    if type(d["qty"]) is not int or d["qty"] <= 0 or type(d["budget_cents"]) is not int or d["budget_cents"] < 0:
        return {"verdict": F, "why": "invalid_qty_or_budget"}
    if not isinstance(d["spec_digest"], str) or len(d["spec_digest"]) != 64:
        return {"verdict": F, "why": "invalid_spec_digest"}
    try:
        date.fromisoformat(d["due_date"])
    except (ValueError, TypeError):
        return {"verdict": F, "why": "invalid_date"}
    if d.get("revoked") is True or d.get("consent_scope") != "coalition_discovery":
        return {"verdict": F, "why": "no_current_discovery_consent"}
    if d.get("source_scope") == "SYNTHETIC_TEST_ONLY":
        return {"verdict": T if demonstration else Z, "why": "synthetic_opt_in_not_live_authority"}
    # Never trust an input record asserting that it verified its own signature.
    # The read-only demo has no independent CRM or signature verifier.
    return {"verdict": Z, "why": "independent_buyer_opt_in_verifier_not_connected"}


def group_demand(demands, *, demonstration=False):
    accepted, rejected = [], []
    seen = set()
    for d in demands:
        v = valid_demand(d, demonstration=demonstration)
        if d.get("id") in seen or d.get("buyer_id") in seen:
            rejected.append({"id": d.get("id"), "verdict": F, "why": "duplicate_buyer_or_request"})
            continue
        seen.update([d.get("id"), d.get("buyer_id")])
        if v["verdict"] != T:
            rejected.append({"id": d.get("id"), **v})
        else:
            accepted.append(d)
    groups = {}
    for d in accepted:
        # Equality is deliberately strict: same exact CAD/spec hash, revision,
        # material and process. An LLM label may not merge distinct parts.
        k = (d["spec_digest"], d["spec_revision"], d["process"], d["material"])
        groups.setdefault(k, []).append(d)
    return {"groups": [
        {"spec_digest": k[0], "spec_revision": k[1], "process": k[2],
         "material": k[3], "buyers": [d["buyer_id"] for d in bs],
         "units": sum(d["qty"] for d in bs), "budget_cents": sum(d["budget_cents"] for d in bs),
         "member_count": len(bs), "demands": bs, "test_only": demonstration}
        for k, bs in groups.items()], "excluded": rejected}


def shortlist_sources(process, *, n=18):
    registry = source_registry()["records"]
    # Conservative broad discovery only. No process-specific capability is proven
    # by a generic marketing page; never silently classify it as a verified shop.
    candidates = [r for r in registry if r["kind"] in
        ("contract_manufacturer", "manufacturing_network", "manufacturing_marketplace", "supplier_directory")]
    return [{**r, "requested_process": process, "exact_process_capability": Z} for r in candidates[:n]]


def verify_ztl_binding(request, receipt=None, verifier=None, *, expected_verifier_pin=None):
    """Truth from external independent verifier only; fields in an untrusted receipt cannot attest themselves.

    verifier is injected from an independently validated ZTL Engineering adapter.
    None means Z. Test stubs must not be used in real deployments.
    """
    h = digest(request)
    if not receipt or verifier is None or not expected_verifier_pin:
        return {"verdict": Z, "why": "ztl_independent_verifier_not_connected", "request_sha256": h}
    mandatory = ("request_sha256", "model_id", "theorem_id", "engine_pin", "epoch", "verifier_pin")
    if any(not receipt.get(k) for k in mandatory) or receipt["request_sha256"] != h:
        return {"verdict": F, "why": "ztl_receipt_missing_or_wrong_request", "request_sha256": h}
    if receipt["verifier_pin"] != expected_verifier_pin:
        return {"verdict": F, "why": "unrecognized_external_verifier"}
    try:
        verified = verifier(request, receipt)
    except Exception:
        return {"verdict": Z, "why": "independent_verifier_error"}
    if verified is not True:
        return {"verdict": F if verified is False else Z,
                "why": "independent_verifier_rejected_or_unknown"}
    return {"verdict": T, "why": "externally_verified_supported_ztl_model_only",
            "model_id": receipt["model_id"], "theorem_id": receipt["theorem_id"],
            "engine_pin": receipt["engine_pin"], "epoch": receipt["epoch"],
            "request_sha256": h}


def evaluate_quote(q, group, *, demonstration):
    """Fixture quote T is *comparative fixture arithmetic*, never a genuine offer."""
    for k in ("route", "spec_digest", "spec_revision", "process", "material", "capacity_units",
              "moq_units", "landed_cents", "due_date", "source_scope"):
        if k not in q:
            return {"verdict": Z, "why": f"quote_missing_{k}"}
    if (q["spec_digest"], q["spec_revision"], q["process"], q["material"]) != (
            group["spec_digest"], group["spec_revision"], group["process"], group["material"]):
        return {"verdict": F, "why": "quote_scope_mismatch"}
    if (type(q["capacity_units"]) is not int or type(q["moq_units"]) is not int or
            type(q["landed_cents"]) is not int or q["landed_cents"] < 0):
        return {"verdict": F, "why": "invalid_quote_amount_or_capacity"}
    if q["moq_units"] > group["units"] or q["capacity_units"] < group["units"]:
        return {"verdict": F, "why": "moq_or_capacity_failure"}
    if q["due_date"] > min(x["due_date"] for x in group["demands"]):
        return {"verdict": F, "why": "late_delivery"}
    if q["source_scope"] == "SYNTHETIC_TEST_ONLY":
        return {"verdict": T if demonstration else Z, "why": "simulated_quote_comparison_only"}
    # External signature verification, supplier identity and fresh capacity
    # must be witnessed by an independent adapter (not installed here).
    return {"verdict": Z, "why": "external_supplier_quote_verifier_not_connected"}


def choose_route(group, offers, *, demonstration=False):
    quotes = []
    denied = []
    for q in offers:
        v = evaluate_quote(q, group, demonstration=demonstration)
        if v["verdict"] == T:
            quotes.append(q)
        else:
            denied.append({"route": q.get("route"), **v})
    quotes.sort(key=lambda q: (q["landed_cents"], q["route"]))
    best = quotes[0] if quotes else None
    # Allocation: integer cents; distribute remainder deterministically.
    allocation = []
    if best:
        total_units = group["units"]
        base = 0
        for i, d in enumerate(group["demands"]):
            val = best["landed_cents"] * d["qty"] // total_units
            allocation.append({"buyer_id": d["buyer_id"], "qty": d["qty"],
                               "allocated_cents": val, "cap_cents": d["budget_cents"]})
            base += val
        # Distinct buyers may have unequal quantities; distribute fractional-cent
        # remainder by buyer ID and ensure each individual cap is rechecked.
        remainder = best["landed_cents"] - base
        for row in sorted(allocation, key=lambda x: x["buyer_id"])[:remainder]:
            row["allocated_cents"] += 1
        if any(x["allocated_cents"] > x["cap_cents"] for x in allocation):
            denied.append({"route": best["route"], "verdict": F, "why": "buyer_individual_budget_exceeded"})
            best = None
    return {"verdict": T if best else Z, "route": best["route"] if best else None,
            "landed_cents": best["landed_cents"] if best else None,
            "allocation": allocation if best else [], "alternatives": [
                {"route": q["route"], "landed_cents": q["landed_cents"]} for q in quotes],
            "rejected": denied, "comparison_scope": "SYNTHETIC_TEST_ONLY" if demonstration else "SUPPLIER_VERIFIED",
            "coalition_needed": bool(best and best["route"] == "COALITION")}


def run_case(case_id):
    cases = read_json("cases.json")
    if case_id not in cases:
        raise ValueError("unknown case")
    case = cases[case_id]
    demo = case.get("test_scope") == "SYNTHETIC_TEST_ONLY"
    gathered = group_demand(case["demands"], demonstration=demo)
    group = gathered["groups"][0] if gathered["groups"] else None
    if group:
        decision = choose_route(group, case["offers"], demonstration=demo)
        eng_request = {"spec_digest": group["spec_digest"], "spec_revision": group["spec_revision"],
                       "process": group["process"], "material": group["material"],
                       "obligation": "engineering_suitability_for_manufacture"}
        eng = verify_ztl_binding(eng_request)
        shortlist = shortlist_sources(group["process"])
    else:
        decision = {"verdict": Z, "route": None, "why": "no_permissioned_compatible_demand"}
        eng = {"verdict": Z, "why": "no_valid_spec_to_verify"}
        shortlist = []
    # Even an attractive numerical candidate is not an admitted contract.
    gates = {"demand_discovery": T if group else Z,
             "route_comparison": decision["verdict"],
             "ztl_engineering": eng["verdict"],
             "cad_dfm": Z, "real_supplier_quote": Z if demo else decision["verdict"],
             "buyer_signatures": Z, "seller_commitment": Z,
             "federation_admission": Z, "paypal_authority": Z,
             "provider_readback": Z}
    proposal = {
        "schema": "legion.industrial.federation-proposal.v1",
        "contract_proposal_hash": digest({"case":case_id,"group":group["spec_digest"] if group else None,
                                          "decision":decision.get("route")}),
        "source_case": case_id, "epoch": 0, "proposed_route": decision.get("route"),
        "buyer_ids": group["buyers"] if group else [],
        "source_scope": "SYNTHETIC_TEST_ONLY" if demo else "REAL_RECORDS",
        "reliance": "NOT_ADMITTED_TO_EXISTING_FEDERATION",
        "external_effects": 0, "paypal_captures_on_this_new_contract": 0,
    }
    return {"case_id": case_id, "title": case["title"], "test_scope": case["test_scope"],
            "source_registry_count": source_registry()["total"], "candidate_suppliers": shortlist,
            "demand": {"group": {k:v for k,v in (group or {}).items() if k != "demands"},
                       "excluded": gathered["excluded"]},
            "route_decision": decision, "engineering": eng, "gates": gates,
            "federation_proposal": proposal,
            "outcome": "SYNTHETIC_ROUTE_CHOSEN_NOT_ADMITTED" if decision.get("route") and demo
                        else "HOLD_MISSING_EVIDENCE",
            "claim": "No real customer orders, provider quotations, manufacturing, or new PayPal payments.",
            "passport_sha256": digest({"proposal":proposal,"gates":gates,"decision":decision})}


def cases_index():
    return [{"id": k, "title": v["title"], "scope": v["test_scope"]} for k,v in read_json("cases.json").items()]


def supplier_rfq(case_id):
    case = read_json("cases.json")[case_id]
    group = group_demand(case["demands"], demonstration=True)["groups"]
    if not group:
        return "NO VALID DISCOVERY-CONSENTED GROUP — NOTHING TO SEND\n"
    g = group[0]
    return ("REQUEST FOR BUDGETARY QUOTE — NOT SENT / NO CONTRACT / NO PURCHASE\n"
            f"Reference: {case_id}\nSpec revision: {g['spec_revision']}\n"
            f"Specification digest: sha256:{g['spec_digest']}\n"
            f"Process: {g['process']} | material: {g['material']} | quantity: {g['units']}\n"
            f"Latest delivery: {min(d['due_date'] for d in g['demands'])}\n"
            "Please specify actual CAD/DFM feasibility, all-in cost, MOQ, capacity, earliest ship date,"
            " applicable certifications, payment terms, quote expiry, and technical exceptions.\n"
            "No private CAD file or buyer contact is disclosed. Buyer identities and requirements"
            " are synthetic fixtures. No order is authorized.\n")
