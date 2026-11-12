"""LEGION Deal Rescue — Judge Mode. One command from a clean clone:

    git clone https://github.com/veraxis-protocol/LEGION-Deal-Rescue.git
    cd LEGION-Deal-Rescue
    python -m scripts.judge_demo

Prerequisites: Python 3.12+ and Git (system). Everything else is installed or fetched and verified automatically:
an isolated .judge_venv with pinned packages, the reBot STEP/readme/performance doc from a pinned Seeed commit
(SHA-256 checked), and ztl-engineer / ztl-stand / ZTL at pinned commits. No API keys, no PayPal credentials.

Options:
  --ci           non-interactive: also run the whole test suite and the browser E2E, then stop (exit 0 only on GO)
  --no-e2e       skip the headless browser acceptance test (the verdict then stays Z for browser_e2e)
  --no-browser   do not open a browser window (the URL is printed)
  --port N       server port (default 8801)
  --full-suite   run the whole unittest suite (Linux: pmix tests need bubblewrap); implied by --ci on Linux
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".judge_venv"
OUT = ROOT / "judge_out"
CACHE = ROOT / ".judge_cache"
LOG = OUT / "CLEAN_CLONE_LOG.txt"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z] {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    with LOG.open("a", encoding="utf-8") as fp:
        fp.write(p.stdout[-20000:] + p.stderr[-20000:] + f"\n[exit {p.returncode}]\n")
    return p


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def unsupported(reason: str, alternative: str) -> int:
    log(f"UNSUPPORTED: {reason}")
    log(f"Alternative: {alternative}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "JUDGE_GO_NO_GO.json").write_text(json.dumps({"final": "F", "unsupported": reason, "alternative": alternative},
                                                        indent=1), encoding="utf-8")
    return 3


def outer(args) -> int:
    """System Python: check prerequisites, build the pinned venv, then continue inside it."""
    if LOG.exists() and not args.keep_log:
        LOG.unlink()
    log(f"LEGION Judge Mode, {platform.system()} {platform.release()} {platform.machine()}, Python {platform.python_version()}")
    if sys.version_info < (3, 12):
        return unsupported(f"Python {platform.python_version()} < 3.12",
                           "install Python 3.12, 3.13 or 3.14 from python.org and run the same command with it")
    if not shutil.which("git"):
        return unsupported("git not found on PATH", "install Git (git-scm.com) and run the same command again")
    if platform.machine().lower() not in ("amd64", "x86_64", "arm64", "aarch64"):
        return unsupported(f"CPU {platform.machine()}: no OpenCascade (cadquery-ocp) wheel",
                           "run on x86_64/arm64 Windows, Linux or macOS, or use the GitHub Actions judge-e2e job")
    if not venv_python().exists():
        log(f"creating isolated environment {VENV.name}")
        venv.EnvBuilder(with_pip=True, clear=True).create(VENV)
    py = str(venv_python())
    reqs = ["-r", "requirements-judge.txt"] + ([] if args.no_e2e else ["-r", "requirements-judge-e2e.txt"])
    p = run([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", *reqs], cwd=ROOT)
    if p.returncode:
        return unsupported("pinned packages could not be installed (see CLEAN_CLONE_LOG.txt)",
                           "check network access to pypi.org; supported: Python 3.12-3.14 on x86_64/arm64")
    if not args.no_e2e:
        cmd = [py, "-m", "playwright", "install", "chromium"]
        if args.ci and platform.system() == "Linux":
            cmd.insert(4, "--with-deps")
        if run(cmd, cwd=ROOT).returncode:
            return unsupported("headless Chromium for the browser E2E could not be installed",
                               "rerun with --no-e2e (browser_e2e stays Z) or use the judge-e2e CI job")
    (OUT / "PIP_FREEZE.txt").write_text(run([py, "-m", "pip", "freeze"], cwd=ROOT).stdout, encoding="utf-8")
    forward = [a for a in sys.argv[1:]] + ["--inner", "--keep-log"]
    log("continuing inside the pinned environment")
    return subprocess.call([py, "-B", "-m", "scripts.judge_demo", *forward], cwd=ROOT)


def wait_ready(url: str, seconds: int = 60) -> bool:
    for _ in range(seconds * 4):
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.25)
    return False


def inner(args) -> int:
    """Inside .judge_venv: preflight, server, browser E2E, verdict."""
    from scripts import judge_preflight
    full = args.full_suite or (args.ci and platform.system() == "Linux")
    log("acceptance preflight: fetch + verify sources, real CAD/BOM/ZTL, commerce replay, PayPal evidence, negatives, tests")
    rc = judge_preflight.main(["--out", str(OUT), "--cache", str(CACHE)] + (["--full-suite"] if full else []))
    go = json.loads((OUT / "JUDGE_GO_NO_GO.json").read_text(encoding="utf-8"))
    log(f"preflight: gates {go.get('gates')}, negatives {go.get('negative_tests')}, skipped_required {go.get('skipped_required')}")
    if "error" in go:
        log(f"STOP: {go['error']}")
        return 2
    fetched = json.loads((OUT / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))["fetched"]
    cad, ztl = fetched["cad"], fetched["ztl"]
    url = f"http://127.0.0.1:{args.port}/"
    cmd = [sys.executable, "-B", "-m", "deal_rescue.server", "--evidence", "demo_evidence", "--port", str(args.port),
           "--cad027-step", cad["step"]["path"], "--cad027-readme", cad["readme"]["path"],
           "--cad027-perf", cad["performance"]["path"], "--ztl-engineer", ztl["ztl-engineer"]["path"],
           "--judge-out", str(OUT)]
    log("$ " + " ".join(cmd))
    srv = subprocess.Popen(cmd, cwd=ROOT, stdout=(OUT / "SERVER.log").open("w"), stderr=subprocess.STDOUT)
    try:
        if not wait_ready(url + "api/runs"):
            log("STOP: server did not start (see SERVER.log)")
            return 4
        log(f"server ready: {url}")
        if not args.no_e2e:
            p = run([sys.executable, "-B", "-m", "scripts.judge_e2e_test", "--base", url, "--out", str(OUT)], cwd=ROOT)
            log((p.stdout.strip().splitlines() or ["(no output)"])[-1])
        go = json.loads((OUT / "JUDGE_GO_NO_GO.json").read_text(encoding="utf-8"))
        log(f"JUDGE_GO_NO_GO final = {go['final']}, gates {go['gates']}")
        log("evidence: " + ", ".join(sorted(p.name for p in OUT.iterdir() if p.is_file())))
        if args.ci:
            return 0 if go["final"] == "T" and rc == 0 else 1
        log(f"Open {url} and click 'Judge walkthrough, drawing to payment' (or {url}#judge=1). Ctrl+C stops the server.")
        if not args.no_browser:
            webbrowser.open(url + "#judge=1")
        srv.wait()
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if srv.poll() is None:
            srv.terminate()
            try:
                srv.wait(timeout=10)
            except subprocess.TimeoutExpired:
                srv.kill()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ci", action="store_true")
    ap.add_argument("--no-e2e", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--full-suite", action="store_true")
    ap.add_argument("--port", type=int, default=8801)
    ap.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--keep-log", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    os.chdir(ROOT)
    return inner(args) if args.inner else outer(args)


if __name__ == "__main__":
    sys.exit(main())
