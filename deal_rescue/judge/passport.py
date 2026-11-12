"""Judge verdict passport (JUDGE_GO_NO_GO.json) and the guards that keep the two cases apart.

CASE A  Real Engineering   reBot STEP -> BOM -> ZTL OPEN -> CAD-025 HOLD -> procurement blocked.
CASE B  Commerce Replay    five buyers -> MOQ 100 -> independent Judge -> five recorded PayPal Sandbox captures.
A payment is evidence for exactly one contract. Nothing here moves a capture from CASE B to CASE A.
"""
from __future__ import annotations

import hashlib
import json

T, F, Z = "T", "F", "Z"
CASE_A_ID = "CASE_A_REBOT_B601_DM_REAL_ENGINEERING"
CASE_B_ID = "CASE_B_SENSOR_MODULE_COMMERCE_REPLAY"
REQUIRED = ("clean_clone", "one_command", "real_cad", "bom", "ztl_runtime", "commerce_workflow",
            "payment_evidence", "browser_e2e", "tests")


class BindingError(ValueError):
    """A payment or receipt was offered for a contract it does not belong to."""


def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def case_a_contract_hash(cad_sha256: str, bom_digest: str, requirements_digest: str) -> str:
    """CASE A has no commercial contract yet; this hash identifies its engineering case only."""
    return canonical_hash({"case": CASE_A_ID, "cad": cad_sha256, "bom": bom_digest, "req": requirements_digest})


def bind_payments(case_contract_hash: str, slots: list) -> dict:
    """Return the captures that belong to ``case_contract_hash``. Any slot from another contract -> BindingError."""
    foreign = [s.get("capture_id") for s in slots if s.get("contract_hash") != case_contract_hash]
    if foreign:
        raise BindingError(f"CONTRACT_MISMATCH: captures {foreign} belong to another contract")
    return {"contract_hash": case_contract_hash, "captures": [s.get("capture_id") for s in slots],
            "provider_confirmed_cents": sum(int(s.get("provider_confirmed_cents") or 0) for s in slots)}


def final_verdict(gates: dict, skipped_required: int) -> str:
    """T only when every required gate is T and no required test was skipped."""
    if skipped_required:
        return F
    vals = [gates.get(k) for k in REQUIRED]
    if any(v == F for v in vals):
        return F
    return T if all(v == T for v in vals) else Z


def verify_against(doc: dict, current: dict) -> list:
    """Stale-evidence check: fields of a recorded JUDGE_GO_NO_GO that no longer match the current run."""
    keys = ("git_commit", "cad_sha256", "source_manifest_sha256", "bom_digest", "requirements_digest")
    return [k for k in keys if doc.get(k) != current.get(k)]
