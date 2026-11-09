"""Build evidence-linked Deal Dossiers for every run in <evidence>/runs, compute the economic case, run the UI evidence
auditor (provenance + claims + N01-N15 matrix), then serve the merchant app. Python 3.11+ standard library only.

  python -B scripts/build_and_serve.py --evidence demo_evidence                 # bundled fresh runs (replay mode)
  python -B scripts/build_and_serve.py --evidence demo_evidence --no-serve      # build + audit only (CI)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(*args):
    r = subprocess.run([sys.executable, "-B", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"FAILED: {' '.join(args)}")
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="demo_evidence")
    ap.add_argument("--counted", default="A2-fresh-2", help="run directory name of the counted fresh run")
    ap.add_argument("--negatives", default="negatives", help="dir with NEGATIVE_RESULTS.json (relative to evidence)")
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--no-serve", action="store_true")
    a = ap.parse_args()
    ev = (ROOT / a.evidence).resolve()
    runs = sorted(p.name for p in (ev / "runs").iterdir() if p.is_dir())
    ids = {}
    for r in runs:
        rid = "WO004-" + r if r.startswith("A2-fresh") else r
        ids[r] = rid
        pay = [x for p in sorted((ev / "paypal_runs").glob("*")) if p.is_dir() for x in ("--paypal-run", str(p))] if (ev / "paypal_runs").exists() else []
        print(sh("-m", "deal_rescue.dossier", "--run", str(ev / "runs" / r), "--mode", "FRESH_SYNTHETIC", "--run-id", rid, "--out", str(ev / "dossier" / rid), *pay))
    counted = ids[a.counted]
    replay = next((ids[r] for r in runs if r != a.counted), counted)
    inf = ev / "runs" / a.counted / "INFERENCE_SUMMARY.json"
    if not inf.exists():
        sys.path.insert(0, str(ROOT / "deal_rescue" / "tools"))
        from inference import usage
        inf.write_text(json.dumps(usage(ev / "runs" / a.counted), indent=1))
    print(sh("deal_rescue/tools/economics.py", str(ev / "dossier" / counted / "DEAL_DOSSIER.json"), str(inf), str(ev)))
    r = subprocess.run([sys.executable, "-B", "-m", "deal_rescue.audit", "--evidence", str(ev), "--counted", counted, "--replay", replay,
                        "--negatives", a.negatives], cwd=ROOT, capture_output=True, text=True)
    print(r.stdout[-1500:])
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit("audit failed")
    rep = json.loads((ev / "UI_PROVENANCE_AUDIT.json").read_text())
    ok = all(v["provenance"]["pass"] and v["claims"]["pass"] for v in rep.values())
    print(json.dumps({"runs": list(ids.values()), "counted": counted, "audit_all_pass": ok}))
    if not ok:
        raise SystemExit(2)
    if not a.no_serve:
        print(f"open http://127.0.0.1:{a.port}/?run={counted}")
        subprocess.run([sys.executable, "-B", "-m", "deal_rescue.server", "--evidence", str(ev), "--port", str(a.port)], cwd=ROOT)


if __name__ == "__main__":
    main()
