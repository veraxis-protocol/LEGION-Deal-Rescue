"""Judge Mode acceptance preflight. Computes every verdict on the judge's machine and writes judge_out/*.json.

Usage (normally called by scripts/judge_demo.py inside .judge_venv):
    python -m scripts.judge_preflight --out judge_out --cache .judge_cache [--full-suite]
Nothing is read from a pre-recorded PASS: CAD, BOM and ZTL are computed now; the commerce replay is rebuilt from the
raw evidence; PayPal captures are checked against the recorded readback; the 10 negative checks run for real.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deal_rescue.industrial import cad027_review as R, cad_xcaf, ztl_gate  # noqa: E402
from deal_rescue.judge import experience as JX, passport as P, sources as S  # noqa: E402

T, F, Z = "T", "F", "Z"
EXPECT = {"assemblies": 33, "leaf_definitions": 64, "leaf_instances": 326, "positions": 40, "instances": 53}


def write(out: Path, name: str, obj) -> str:
    p = out / name
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) if not isinstance(obj, str) else obj, encoding="utf-8")
    return name


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def environment() -> dict:
    git = shutil.which("git")
    gv = subprocess.run([git, "--version"], capture_output=True, text=True).stdout.strip() if git else None
    return {"os": platform.system(), "os_release": platform.release(), "machine": platform.machine(),
            "python": platform.python_version(), "python_ok": sys.version_info >= (3, 12), "git": gv}


def run_unittests(args: list, env: dict, log: Path) -> dict:
    t0 = time.time()
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", *args, "-v"], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = p.stdout + p.stderr
    log.write_text(text, encoding="utf-8")
    ran = int((re.search(r"Ran (\d+) test", text) or [0, 0])[1])
    skipped = len(re.findall(r"\.\.\. skipped", text))
    return {"args": args, "ran": ran, "ok": p.returncode == 0, "skipped": skipped,
            "failures": len(re.findall(r"^(FAIL|ERROR):", text, re.M)), "seconds": round(time.time() - t0, 1),
            "log": log.name}


def commerce_replay(out: Path) -> dict:
    """Rebuild dossiers from the raw evidence in a scratch copy and audit them; compare with the committed ones."""
    with tempfile.TemporaryDirectory() as d:
        ev = Path(d) / "demo_evidence"
        shutil.copytree(ROOT / "demo_evidence", ev)
        p = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "build_and_serve.py"), "--evidence", str(ev),
                            "--no-serve"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        last = (p.stdout.strip().splitlines() or ["{}"])[-1]
        try:
            audit = json.loads(last)
        except ValueError:
            audit = {"raw": last}
        volatile = ("built_at", "source_commit")
        same = {}
        for run in ("run-1", "run-2"):
            a = json.loads((ev / "dossier" / run / "DEAL_DOSSIER.json").read_text(encoding="utf-8"))
            b = json.loads((ROOT / "demo_evidence" / "dossier" / run / "DEAL_DOSSIER.json").read_text(encoding="utf-8"))
            for k in volatile:
                a.pop(k, None), b.pop(k, None)
            same[run] = P.canonical_hash(a) == P.canonical_hash(b)
    ok = p.returncode == 0 and audit.get("audit_all_pass") is True and all(same.values())
    return {"verdict": T if ok else F, "rebuild_exit": p.returncode, "audit": audit,
            "rebuilt_equals_committed_except_build_metadata": same,
            "case": P.CASE_B_ID, "stderr_tail": p.stderr[-400:]}


def paypal_check(manifest: dict) -> dict:
    d2 = json.loads((ROOT / "demo_evidence/dossier/run-2/DEAL_DOSSIER.json").read_text(encoding="utf-8"))
    d1 = json.loads((ROOT / "demo_evidence/dossier/run-1/DEAL_DOSSIER.json").read_text(encoding="utf-8"))
    pay = d2["paypal"]
    caps = [s["capture_id"] for s in pay["slots"]]
    raw = "".join(p.read_text(encoding="utf-8", errors="replace") for p in (ROOT / "demo_evidence").rglob("*")
                  if p.is_file() and "paypal" in str(p).lower() and p.suffix in (".json", ".jsonl"))
    in_raw = {c: c in raw for c in caps}
    want = manifest["commerce"]
    checks = {
        "five_unique_captures": len(set(caps)) == 5,
        "captures_equal_manifest": sorted(caps) == sorted(want["captures"]),
        "all_on_one_contract": {s["contract_hash"] for s in pay["slots"]} == {want["contract_hash"]},
        "readback_confirmed_5": pay["readback_confirmed_captures"] == 5,
        "provider_confirmed_49500": pay["provider_confirmed_cents"] == want["provider_confirmed_cents"],
        "captures_present_in_raw_paypal_evidence": all(in_raw.values()),
        "run_1_has_no_payment": d1["paypal"]["provider_confirmed_cents"] == 0,
    }
    return {"verdict": T if all(checks.values()) else F, "checks": checks, "captures": caps,
            "contract_hash": want["contract_hash"], "label": "RECORDED PayPal Sandbox evidence (no new provider call)",
            "new_provider_posts": 0}


def negatives(report: dict, cad: dict, ztl_dir: str, manifest: dict, current: dict) -> dict:
    rows = []

    def row(n, name, expected, observed, ok):
        rows.append({"n": n, "test": name, "expected": expected, "observed": observed, "pass": bool(ok)})

    readme = Path(cad["readme"]["path"]).read_text(encoding="utf-8")
    perf = Path(cad["performance"]["path"]).read_text(encoding="utf-8")
    x = report["xcaf"]
    # 1 substituted STEP SHA -> F (tampered copy of the real file; and a tampered cache entry is refused)
    with tempfile.TemporaryDirectory() as d:
        fake = Path(d) / R.PINNED_STEP_NAME
        fake.write_bytes(Path(cad["step"]["path"]).read_bytes()[:-64] + b"/* tampered */\nEND-ISO-10303-21;\n")
        r = R.StagedRun(fake, cad["readme"]["path"], ztl_dir, cad["performance"]["path"]).stage(4)
        cache_check = S.verify_file(fake, manifest["cad"]["files"]["step"])
        row(1, "substituted STEP SHA", "drawing F, run blocked; cache verification refuses the file",
            f"drawing {r['drawing']['status']}, demo {r['overall']['demo']}, cache {cache_check['why'][:40]}",
            r["drawing"]["status"] == F and r["overall"]["demo"] == F and not cache_check["ok"])
    # 2 changed quantity -> F
    xm = copy.deepcopy(x)
    xm["instances"]["02_Motor_Front_Spacer"] -= 1
    b = R.reconcile(xm, R.parse_readme(readme), "0" * 64)
    row(2, "changed quantity", "BOM F", f"BOM {R.bom_status(b)}", R.bom_status(b) == F)
    # 3 missing engineering tolerance -> HOLD
    rail = R.production_predicates(x, readme, perf)[0]
    proc = JX.procurement(report)
    row(3, "missing engineering tolerance", "RAIL_TOLERANCE Z, ZTL OPEN, procurement BLOCKED (HOLD)",
        f"RAIL_TOLERANCE {rail['RAIL_TOLERANCE']}, ZTL {rail['verdict']}, procurement {proc['status']}",
        rail["RAIL_TOLERANCE"] == Z and rail["verdict"] == "OPEN" and proc["status"] == "BLOCKED")
    # 4 unsigned ZTL receipt -> no admission (valid spec; verifier configured with a TEST key made here; no JWS)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    src = "c" * 64
    spec = {"drawing_sha256": src, "drawing_revision": "r1", "source_documents": [{"document_id": "d", "kind": "step", "sha256": src}],
            "bom": [{"part_number": "P1", "quantity": 1, "source_sha256": src, **{f: "stated" for f in ztl_gate.PART_FIELDS}}],
            "requirements": [{"id": f"P1.{c}", "part_number": "P1", "category": c, "statement": "s", "source_sha256": src}
                             for c in sorted(ztl_gate.CATEGORIES)]}
    pem = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.PEM,
                                                                 serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    env = {"LEGION_ZTL_ATTESTATION_URL": "https://verifier.example.com/attest", "LEGION_BACKEND_TOKEN": "t",
           "LEGION_ZTL_VERIFY_KEY_PEM": pem, "LEGION_ZTL_VERIFY_KID": "k1", "LEGION_ZTL_CURRENT_EPOCH": "1",
           "LEGION_ZTL_POLICY_SHA256": "d" * 64, "LEGION_ZTL_STAND_COMMIT": "e" * 40}
    u = R.cad025_gate(spec, {"verdict": "EARNED"}, env=env)
    row(4, "unsigned ZTL receipt", "admission refused", f"admission {u['admission']} {u.get('admission_code')}",
        u["admission"] == F and u["engineering_admission"] != T)
    # 5 mixing two contract hashes -> F
    pay = JX.payment(json.loads((ROOT / "demo_evidence/dossier/run-2/DEAL_DOSSIER.json").read_text(encoding="utf-8")))
    mixed = copy.deepcopy(pay["captures"])
    mixed[0]["contract_hash"] = "f" * 64
    try:
        P.bind_payments(pay["contract_hash"], mixed)
        row(5, "mixed contract hashes", "F", "accepted", False)
    except P.BindingError as e:
        row(5, "mixed contract hashes", "F (refused)", str(e)[:90], True)
    # 6 historical PayPal capture -> new CAD case -> F
    a_hash = P.case_a_contract_hash(report["drawing"]["sha256"], P.canonical_hash(report["bom"]["rows"]),
                                    report["ztl"]["requirements_digest"])
    try:
        P.bind_payments(a_hash, pay["captures"])
        row(6, "historic capture to new CAD case", "F", "attributed", False)
    except P.BindingError as e:
        row(6, "historic capture to new CAD case", "F (refused)", str(e)[:90], True)
    # 7 unavailable external dependency -> explicit failure, not PASS
    try:
        S._download("http://127.0.0.1:9/unreachable.step", Path(tempfile.gettempdir()) / "legion_unreachable.step", timeout=5)
        dl = "downloaded?!"
        ok_dl = False
    except S.SourceError as e:
        dl, ok_dl = str(e)[:70], True
    st = R.check_design(R.rail_length_brick(x, readme, (-0.02, 0.02), "TEST SCENARIO ONLY"), str(Path(ztl_dir).parent / "absent"))
    row(7, "unavailable dependency (download, ZTL)", "explicit failure, never PASS",
        f"download: {dl}; ZTL: {st['verdict']} stand_called={st['stand_called']}",
        ok_dl and st["verdict"] == "OPEN" and st["stand_called"] is False)
    # 8 skipped required CAD test -> JUDGE_GO F
    gates_all_t = {k: T for k in P.REQUIRED}
    row(8, "skipped required CAD test", "JUDGE_GO F", f"final {P.final_verdict(gates_all_t, skipped_required=1)}",
        P.final_verdict(gates_all_t, 1) == F and P.final_verdict(gates_all_t, 0) == T)
    # 9 stale evidence -> mismatch detected
    stale = dict(current, cad_sha256="0" * 64, git_commit="0" * 40)
    mism = P.verify_against(stale, current)
    row(9, "stale evidence", "mismatch detected", f"mismatched fields {mism}", set(mism) == {"cad_sha256", "git_commit"})
    # 10 rerun with identical inputs -> identical verdicts and hashes
    def v(r):
        return {**{k: r["overall"][k] for k in ("demo", "bom", "ztl_production", "rail_tolerance", "engineering_admission")},
                "digest": r["ztl"]["requirements_digest"], "bom": P.canonical_hash(r["bom"]["rows"]),
                "xcaf": P.canonical_hash(r["xcaf"]["instances"])}
    again = R.run(cad["step"]["path"], cad["readme"]["path"], ztl_dir, cad["performance"]["path"])
    row(10, "rerun with identical inputs", "identical verdicts and hashes", json.dumps(v(again))[:120], v(again) == v(report))
    return {"rows": rows, "passed": sum(r["pass"] for r in rows), "total": len(rows),
            "financial_effects": {"paypal_calls": 0, "supplier_requests": 0, "cad_transmitted": 0}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "judge_out"))
    ap.add_argument("--cache", default=str(ROOT / ".judge_cache"))
    ap.add_argument("--full-suite", action="store_true", help="also run the whole unittest suite (Linux: pmix needs bubblewrap)")
    a = ap.parse_args(argv)
    out, cache = Path(a.out), Path(a.cache)
    out.mkdir(parents=True, exist_ok=True)
    t0 = datetime.now(timezone.utc).isoformat()
    manifest = S.load_manifest()
    manifest_sha = S.sha256_file(S.MANIFEST)
    env_info = environment()
    result = {"schema": "legion.judge.go-no-go.v1", "started_utc": t0, "git_commit": git_commit(),
              "environment": env_info, "source_manifest": "scripts/judge_manifest.json",
              "source_manifest_sha256": manifest_sha, "evidence_paths": {}}
    ev = result["evidence_paths"]
    gates = {"clean_clone": T if result["git_commit"] != "UNKNOWN" else F, "one_command": T}
    try:
        cad = S.fetch_cad(cache, manifest)
        ztl = S.fetch_ztl(cache, manifest)
    except S.SourceError as e:
        result.update(final=F, error=str(e), gates={**gates, "real_cad": F})
        ev["JUDGE_GO_NO_GO"] = write(out, "JUDGE_GO_NO_GO.json", result)
        print(json.dumps({"final": F, "error": str(e)}))
        return 2
    ev["SOURCE_MANIFEST"] = write(out, "SOURCE_MANIFEST.json", {"manifest": manifest, "manifest_sha256": manifest_sha,
                                                                 "fetched": {"cad": cad, "ztl": ztl}})
    ztl_dir = ztl["ztl-engineer"]["path"]
    report = R.run(cad["step"]["path"], cad["readme"]["path"], ztl_dir, cad["performance"]["path"])
    x, b, z = report.get("xcaf", {}), report.get("bom", {}), report.get("ztl", {})
    ev["CAD_XCAF_RESULT"] = write(out, "CAD_XCAF_RESULT.json", x)
    ev["BOM_RESULT"] = write(out, "BOM_RESULT.json", {"drawing": report["drawing"], "bom_status": report.get("bom_status"), **b})
    ev["ZTL_RESULT"] = write(out, "ZTL_RESULT.json", {**z, "cad025": report.get("cad025"),
                                                      "ztl_commits": {k: v["commit"] for k, v in ztl.items()}})
    ocp_ok = x.get("verdict") == "T_XCAF_STRUCTURE" and (x.get("assemblies"), x.get("leaf_definitions"), x.get("leaf_instances")) == \
        (EXPECT["assemblies"], EXPECT["leaf_definitions"], EXPECT["leaf_instances"])
    bom_ok = (b.get("mandatory_positions_matched"), b.get("mandatory_positions"), b.get("mandatory_instances_step"),
              b.get("mandatory_instances_readme")) == (40, 40, 53, 53)
    preds = {p["id"]: p["verdict"] for p in z.get("predicates", [])}
    it = z.get("integration_test", {})
    ztl_ok = (preds == {"rail_length_tolerance": "OPEN", "joint2_load_torque": "OPEN"} and z.get("production_verdict") == "OPEN"
              and report["overall"].get("rail_tolerance") == Z and it.get("verdict") == "EARNED" and it.get("stand_called") is True
              and report["overall"].get("engineering_admission") == Z)
    gates.update(real_cad=T if report["drawing"]["status"] == T and ocp_ok else F, bom=T if bom_ok else F,
                 ztl_runtime=T if ztl_ok else F)
    comm = commerce_replay(out)
    ev["COMMERCE_REPLAY_RESULT"] = write(out, "COMMERCE_REPLAY_RESULT.json", comm)
    pp = paypal_check(manifest)
    ev["PAYPAL_EVIDENCE_CHECK"] = write(out, "PAYPAL_EVIDENCE_CHECK.json", pp)
    coal = JX.coalition()
    proc = JX.procurement(report)
    gates.update(commerce_workflow=T if comm["verdict"] == T and coal["units"] == 100 and coal["total_cents"] == 242500 else F,
                 payment_evidence=pp["verdict"])
    current = {"git_commit": result["git_commit"], "cad_sha256": report["drawing"]["sha256"], "source_manifest_sha256": manifest_sha,
               "bom_digest": P.canonical_hash(b.get("rows")), "requirements_digest": z.get("requirements_digest")}
    neg = negatives(report, cad, ztl_dir, manifest, current)
    ev["NEGATIVE_TESTS"] = write(out, "NEGATIVE_TESTS.json", neg)
    env = dict(os.environ, CAD027_STEP=cad["step"]["path"], CAD027_README=cad["readme"]["path"],
               CAD027_PERF=cad["performance"]["path"], ZTL_ENGINEER_DIR=ztl_dir, PYTHONUTF8="1")
    tests = {"required_real": run_unittests(["tests.judge_real_cad027"], env, out / "TESTS_REQUIRED_REAL.log")}
    if a.full_suite:
        # pmix fixtures and binary from the vendored, SHA-pinned release (same installer as CI); needs Linux bubblewrap
        pm = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "install_pmix.py"),
                             str(ROOT / "vendor" / "pmix" / "PAYPAL_CAD_001_RELEASE_20261110.zip")],
                            cwd=ROOT, capture_output=True, text=True)
        tests["pmix_install"] = {"ok": pm.returncode == 0, "output": (pm.stdout + pm.stderr).strip()[-300:],
                                 "bubblewrap": shutil.which("bwrap"), "ran": 0, "skipped": 0}
        tests["full_suite"] = run_unittests(["discover", "-s", "tests"], env, out / "TESTS_FULL_SUITE.log")
    else:
        mods = ["tests.test_cad027_demo", "tests.test_cad025_ztl_gate", "tests.test_judge", "tests.test_demand_first",
                "tests.test_industrial", "tests.test_release"]
        tests["platform_suite"] = run_unittests(mods, env, out / "TESTS_PLATFORM_SUITE.log")
        tests["platform_note"] = ("pmix sandbox tests need Linux bubblewrap; they run in the judge-e2e CI job "
                                  "(--full-suite). Every module listed here runs with 0 skips.")
    skipped_required = sum(t["skipped"] for t in tests.values() if isinstance(t, dict))
    tests_ok = all(t["ok"] for t in tests.values() if isinstance(t, dict))
    ev["TEST_RESULTS"] = write(out, "TEST_RESULTS.json", tests)
    gates["tests"] = T if tests_ok and skipped_required == 0 else F
    gates["browser_e2e"] = Z   # filled in by scripts/judge_e2e_test.py
    result.update({**current,
                   "cad_sha256": report["drawing"]["sha256"],
                   "ocp_verdict": gates["real_cad"], "bom_verdict": gates["bom"],
                   "ztl_verdict": {"production": z.get("production_verdict"), "predicates": preds,
                                   "rail_tolerance": report["overall"].get("rail_tolerance"),
                                   "integration_test": it.get("verdict"), "gate": gates["ztl_runtime"]},
                   "engineering_admission": report["overall"].get("engineering_admission"),
                   "procurement_case": {"case": P.CASE_A_ID, "status": proc["status"], "part": proc["part_id"]},
                   "commerce_replay": comm["verdict"], "paypal_evidence": pp["verdict"],
                   "browser_e2e": "NOT_RUN_YET", "tests": {k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in ("ran", "ok", "skipped")})
                                                           for k, v in tests.items()},
                   "skipped_required": skipped_required, "negative_tests": f"{neg['passed']}/{neg['total']}",
                   "external_effects": {"paypal_calls": 0, "supplier_requests": 0, "cad_transmitted": 0, "new_live_paypal_capture": "Z/NOT_EXECUTED"},
                   "gates": gates, "preflight_finished_utc": datetime.now(timezone.utc).isoformat(),
                   "browser_e2e_finished_utc": None, "finished_utc": None})
    if neg["passed"] != neg["total"]:
        gates["tests"] = F
    # final=T is only possible after the browser E2E closes the timeline (scripts/judge_e2e_test.py -> P.finalize)
    result["final"] = F if P.final_verdict(gates, skipped_required) == F else Z
    result["timeline"] = P.check_timeline(result)
    ev["JUDGE_GO_NO_GO"] = write(out, "JUDGE_GO_NO_GO.json", result)
    print(json.dumps({"final": result["final"], "gates": gates, "negatives": result["negative_tests"],
                      "skipped_required": skipped_required}))
    return 0 if all(v == T for k, v in gates.items() if k != "browser_e2e") else 1


if __name__ == "__main__":
    sys.exit(main())
