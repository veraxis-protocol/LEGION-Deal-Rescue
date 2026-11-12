"""Browser E2E for Judge Mode: headless Chromium walks all 7 screens at 1280x720 and 1440x900 against the running
server, checks every number against the server's JSON, records console errors and failed requests, saves
screenshots, and writes BROWSER_E2E_RESULT.json + updates JUDGE_GO_NO_GO.json (browser_e2e, final).

    python -m scripts.judge_e2e_test --base http://127.0.0.1:8801/ --out judge_out
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deal_rescue.judge import passport as P  # noqa: E402

VIEWPORTS = [(1280, 720), (1440, 900)]
STEPS = ["drawing", "parts", "engineering", "procurement", "coalition", "payment", "result"]


def walk(page, base: str, shots: Path, vp: str) -> list:
    checks = []

    def check(step, name, ok, detail=""):
        checks.append({"viewport": vp, "step": step, "check": name, "pass": bool(ok), "detail": str(detail)[:200]})

    def api(path):
        r = page.request.get(base + path.lstrip("/"))
        return r.status, (r.json() if "json" in (r.headers.get("content-type") or "") else r.text())

    def step_done(i, wait_for):
        page.wait_for_selector(wait_for, timeout=180000)
        page.screenshot(path=str(shots / f"{vp}_{i + 1}_{STEPS[i]}.png"), full_page=False)

    def go_next():
        page.click("#jx-next")

    page.goto(base, wait_until="networkidle")
    check("home", "original UI loads", "LEGION" in page.title() or page.locator("header").count() > 0)
    check("home", "judge button present", page.locator("#legion-judge").count() == 1)
    check("home", "CAD button state is explained (configured)", "not configured" not in page.inner_text("#legion-cad027"))
    page.click("#legion-judge")
    step_done(0, "text=matches the pinned source")
    st, s1 = api("/api/industrial/cad027/stage?n=1")
    check("drawing", "SHA shown equals server JSON and pin", s1["drawing"]["sha256"] in page.inner_text("#jx-body")
          and s1["drawing"]["sha256"] == "a1e301ee03d46589e26d3fc2272d19ba53c1878f0104274695e5c9a88aa512d2", s1["drawing"]["sha256"])
    go_next()
    step_done(1, "#jx-xcaf")
    _, s2 = api("/api/industrial/cad027/stage?n=2")
    x, b = s2["xcaf"], s2["bom"]
    xt, bt = page.inner_text("#jx-xcaf"), page.inner_text("#jx-bom")
    check("parts", "XCAF 33/64/326 shown = JSON", (x["assemblies"], x["leaf_definitions"], x["leaf_instances"]) == (33, 64, 326)
          and f"{x['assemblies']} sub-assemblies" in xt and f"{x['leaf_instances']} instances" in xt, xt)
    check("parts", "BOM 40/40 53/53 shown = JSON", (b["mandatory_positions_matched"], b["mandatory_positions"],
                                                     b["mandatory_instances_step"], b["mandatory_instances_readme"]) == (40, 40, 53, 53)
          and "40/40 parts" in bt and "53/53 instances" in bt, bt)
    go_next()
    step_done(2, "#jx-adm")
    _, s3 = api("/api/industrial/cad027/stage?n=3")
    body = page.inner_text("#jx-body")
    preds = {p["id"]: p["verdict"] for p in s3["ztl"]["predicates"]}
    check("engineering", "reBot ZTL OPEN, both predicates OPEN (JSON)", s3["ztl"]["production_verdict"] == "OPEN"
          and preds == {"rail_length_tolerance": "OPEN", "joint2_load_torque": "OPEN"}, preds)
    check("engineering", "RAIL_TOLERANCE Z shown", "RAIL_TOLERANCE" in body and "OPEN" in page.inner_text("#jx-ztl"))
    check("engineering", "integration test labelled NOT reBot, EARNED by real stand",
          "NOT a reBot check" in body and s3["ztl"]["integration_test"]["verdict"] == "EARNED"
          and s3["ztl"]["integration_test"]["stand_called"] is True)
    check("engineering", "ENGINEERING_ADMISSION Z", page.inner_text("#jx-adm").strip() == "Z" and s3["cad025"]["engineering_admission"] == "Z")
    go_next()
    step_done(3, "#jx-proc")
    check("procurement", "procurement BLOCKED until admission", "BLOCKED" in page.inner_text("#jx-proc"))
    check("procurement", "RFQ not sent, CAD not attached", "sent: no" in page.inner_text("#jx-body") and "CAD attached: no" in page.inner_text("#jx-body"))
    go_next()
    step_done(4, "#jx-coal")
    _, coal = api("/api/judge/coalition")
    check("coalition", "5 x 20 -> 100/100, $2,425.00 (JSON)", coal["units"] == 100 and len(coal["requests"]) == 5
          and all(r["qty"] == 20 for r in coal["requests"]) and coal["total_cents"] == 242500
          and "100/100 units" in page.inner_text("#jx-coal") and "$2,425.00" in page.inner_text("#jx-body"), coal["total_cents"])
    check("coalition", "labelled SYNTHETIC", "SYNTHETIC" in page.inner_text("#jx-body"))
    go_next()
    step_done(5, "#jx-pay")
    _, pay = api("/api/judge/payment")
    pb = page.inner_text("#jx-body")
    check("payment", "5/5 readback captures, $495.00 (JSON)", pay["readback_confirmed_captures"] == 5
          and pay["provider_confirmed_cents"] == 49500 and "5/5 readback-confirmed" in page.inner_text("#jx-pay")
          and "$495.00" in page.inner_text("#jx-pay"))
    check("payment", "every capture id shown", all(s["capture_id"] in pb for s in pay["captures"]))
    check("payment", "labelled CASE B recorded Sandbox replay", "CASE B" in pb and "Sandbox" in pb)
    go_next()
    step_done(6, "#jx-cross")
    _, res = api("/api/judge/result")
    check("result", "CASE B captures refused for CASE A", res["cross_case_payment_attribution"].startswith("REFUSED")
          and "REFUSED" in page.inner_text("#jx-cross"))
    check("result", "CASE A payments 0, procurement BLOCKED", res["case_a"]["payments"] == 0 and res["case_a"]["procurement"] == "BLOCKED")
    st_ev, _ = api("/api/judge/evidence?name=JUDGE_GO_NO_GO.json")
    check("result", "evidence link serves JUDGE_GO_NO_GO.json", st_ev == 200, st_ev)
    st_rep, rep = api("/api/industrial/cad027/report.json")
    check("result", "JSON report of the current run downloadable", st_rep == 200 and rep.get("stage") == 4, st_rep)
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", default=str(ROOT / "judge_out"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    shots = out / "SCREENSHOTS"
    shots.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    result = {"schema": "legion.judge.browser-e2e.v1", "base": a.base, "started_utc": datetime.now(timezone.utc).isoformat(),
              "viewports": [], "checks": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for w, h in VIEWPORTS:
            vp = f"{w}x{h}"
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            errors, failed = [], []
            page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            page.on("response", lambda r, f=failed: f.append(f"{r.status} {r.url}") if r.status >= 400 else None)
            try:
                checks = walk(page, a.base, shots, vp)
            except Exception as exc:          # a broken screen is a failed E2E, recorded with its reason
                checks = [{"viewport": vp, "step": "walk", "check": "completed", "pass": False, "detail": repr(exc)[:300]}]
                page.screenshot(path=str(shots / f"{vp}_FAILURE.png"))
            result["checks"] += checks
            result["viewports"].append({"viewport": vp, "console_errors": errors, "failed_requests": failed,
                                        "checks": len(checks), "passed": sum(c["pass"] for c in checks)})
            ctx.close()
        browser.close()
    ok = all(c["pass"] for c in result["checks"]) and all(not v["console_errors"] and not v["failed_requests"]
                                                         for v in result["viewports"])
    result.update(verdict="T" if ok else "F", passed=sum(c["pass"] for c in result["checks"]), total=len(result["checks"]),
                  screenshots=sorted(p.name for p in shots.glob("*.png")), finished_utc=datetime.now(timezone.utc).isoformat())
    (out / "BROWSER_E2E_RESULT.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    gp = out / "JUDGE_GO_NO_GO.json"
    if gp.is_file():
        go = json.loads(gp.read_text(encoding="utf-8"))
        browser = {"verdict": result["verdict"], "checks": f"{result['passed']}/{result['total']}",
                   "console_errors": sum(len(v["console_errors"]) for v in result["viewports"]),
                   "failed_requests": sum(len(v["failed_requests"]) for v in result["viewports"]),
                   "screenshots": len(result["screenshots"]), "finished_utc": result["finished_utc"]}
        # finished_utc is set only now, after the browser result has been checked
        go = P.finalize(go, browser, datetime.now(timezone.utc).isoformat())
        gp.write_text(json.dumps(go, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"browser_e2e": result["verdict"], "checks": f"{result['passed']}/{result['total']}",
                      "console_errors": [v["console_errors"] for v in result["viewports"]]}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
