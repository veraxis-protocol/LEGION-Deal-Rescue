"""LEGION Deal Rescue - local read-only product server.

Serves the merchant UI and the run-linked evidence. It has no write path: no model calls, no PayPal calls,
no mutation of run files. `--mode replay` is the only mode implemented here (payments are made by a separately authorized process).

  python -B -m deal_rescue.server --evidence wo004_evidence --port 8795
"""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64
import binascii
import secrets
from deal_rescue.industrial import core as industrial, workflow as industrial_flow, demo_intent, cad_bom, ztl_gate
from deal_rescue.industrial import admission as commerce_admission
from deal_rescue.industrial import cad027_review
from urllib.parse import parse_qs, urlparse

WEB = Path(__file__).parent / "web"
EV = None
DEMO_SESSIONS = {}
DEMO_LEDGER = None
CAD027 = None  # cad027_review.StagedRun when --cad027-step is given
JUDGE_OUT = None  # Path of judge_out/ when started by scripts/judge_demo.py
JUDGE_EVIDENCE = ("JUDGE_GO_NO_GO.json", "SOURCE_MANIFEST.json", "CAD_XCAF_RESULT.json", "BOM_RESULT.json", "ZTL_RESULT.json",
                  "COMMERCE_REPLAY_RESULT.json", "PAYPAL_EVIDENCE_CHECK.json", "NEGATIVE_TESTS.json", "TEST_RESULTS.json",
                  "CLEAN_CLONE_LOG.txt", "BROWSER_E2E_RESULT.json")
RUNS = {}  # run_id -> (run_dir, dossier_dir)


def resolve_ref(run_dir, ref):
    """ref = 'FILE#seq' (records carrying seq) or 'FILE@line' (0-based line)."""
    if "#" in ref:
        f, s = ref.split("#", 1)
        key, val = "seq", int(s)
    else:
        f, s = ref.split("@", 1)
        key, val = "line", int(s)
    p = (run_dir / f).resolve()
    if run_dir.resolve() not in p.parents:
        raise ValueError("ref outside run")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[val] if key == "line" else next(r for r in rows if r.get("seq") == val)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", extra=None):
        b = body if isinstance(body, bytes) else json.dumps(body, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        """Only bounded in-memory CAD intake + optional DEMO intent. No provider POST."""
        u = urlparse(self.path)
        if u.path not in ("/api/industrial/intake", "/api/industrial/engineering-extract", "/api/industrial/demo-confirm",
                          "/api/industrial/ztl-admission", "/api/industrial/procurement-request"):
            return self.send(405, {"error":"METHOD_NOT_ALLOWED"})
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self.send(415, {"error":"JSON_ONLY"})
        origin=self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:"+str(self.server.server_port),
                                    "http://localhost:"+str(self.server.server_port)):
            return self.send(403, {"error":"CROSS_ORIGIN_POST_DENIED"})
        try:
            size=int(self.headers.get("Content-Length", "-1"))
            limit=23000000 if u.path in ("/api/industrial/engineering-extract","/api/industrial/intake") else 100000 if u.path in ("/api/industrial/ztl-admission", "/api/industrial/procurement-request") else 2900000
            if not 0<size<=limit: return self.send(413,{"error":"REQUEST_TOO_LARGE"})
            self.connection.settimeout(10)
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):return self.send(400,{"error":"OBJECT_EXPECTED"})
            if u.path in ("/api/industrial/ztl-admission", "/api/industrial/procurement-request"):
                try:
                    proof=ztl_gate.engineering_admission(body.get('contract_id'), body.get('spec'))
                except ztl_gate.GateError as exc:
                    return self.send(exc.status, ztl_gate.denial(exc))
                if u.path == "/api/industrial/procurement-request":
                    # The existing Deal Rescue server is a REPLAY server. A valid
                    # engineering certificate is necessary but not sufficient for an
                    # order: all ten separate commerce obligations remain closed.
                    decision=commerce_admission.decide(body.get('commercial_context'),
                                                       body.get('commercial_receipts'))
                    return self.send(409, {'engineering_admission':'T',
                                           'code':'COMMERCIAL_EXECUTION_NOT_AUTHORIZED',
                                           'commerce_verdict':decision['verdict'],
                                           'commerce_obligations':decision.get('gates'),
                                           'procurement_authorized':False,
                                           'payment_authorized':False,
                                           'supplier_requests_sent':0,'paypal_captures':0})
                return self.send(200, {'engineering_admission':'T', 'proof':proof,
                                       'procurement_authorized':False,
                                       'payment_authorized':False,
                                       'supplier_requests_sent':0,'paypal_captures':0})
            if u.path in ("/api/industrial/intake","/api/industrial/engineering-extract"):
                raw=base64.b64decode(body.get("file_b64", ""),validate=True)
                filename=body.get('filename','')
                is_step=isinstance(filename,str) and filename.lower().endswith(('.step','.stp'))
                if len(raw)>(16777216 if is_step else 2097152):return self.send(413,{"error":"FILE_TOO_LARGE"})
                if u.path=="/api/industrial/engineering-extract":
                    return self.send(200,cad_bom.extract(filename,raw))
                result=industrial_flow.run_intake(body.get("filename",""),raw,body.get("claim",{}))
                if result['overall']=="DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY":
                    session=secrets.token_urlsafe(24)
                    if len(DEMO_SESSIONS)>128:DEMO_SESSIONS.clear()
                    DEMO_SESSIONS[session]={'response':result}
                    result['demo_session']=session
                return self.send(200,result)
            if DEMO_LEDGER is None:
                return self.send(403,{"error":"DEMO_INTENTS_DISABLED"})
            session=DEMO_SESSIONS.get(body.get('demo_session'))
            return self.send(200,demo_intent.record(session,body,DEMO_LEDGER))
        except (ValueError,TypeError,KeyError,binascii.Error,UnicodeError) as exc:
            return self.send(422,{"error":type(exc).__name__,"code":str(exc)[:160]})
        except Exception:
            return self.send(500,{"error":"INTERNAL_INTAKE_ERROR"})

    def judge_get(self, path, q):
        """Judge Experience API (read-only). Every answer is computed from the current run or recorded evidence."""
        from deal_rescue.judge import experience as JX
        if path == "/api/judge/state":
            return self.send(200, {"cad": cad027_review.cad_status(CAD027), "judge_out": bool(JUDGE_OUT),
                                   "cases": {"A": JX.P.CASE_A_ID, "B": JX.P.CASE_B_ID}})
        report = CAD027.report if CAD027 else None
        if path == "/api/judge/procurement":
            if not (report and report.get("stage", 0) >= 3):
                return self.send(409, {"error": "RUN_ENGINEERING_REVIEW_FIRST",
                                       "action": "complete DRAWING, PARTS and ENGINEERING REVIEW"})
            return self.send(200, JX.procurement(report, q.get("part")))
        if path == "/api/judge/coalition":
            return self.send(200, JX.coalition())
        if path == "/api/judge/payment":
            return self.send(200, JX.payment(json.loads((RUNS["run-2"][1] / "DEAL_DOSSIER.json").read_text(encoding="utf-8"))))
        if path == "/api/judge/result":
            if not (report and report.get("stage") == 4):
                return self.send(409, {"error": "RUN_ALL_ENGINEERING_STEPS_FIRST"})
            pay = JX.payment(json.loads((RUNS["run-2"][1] / "DEAL_DOSSIER.json").read_text(encoding="utf-8")))
            go = json.loads((JUDGE_OUT / "JUDGE_GO_NO_GO.json").read_text(encoding="utf-8"))                 if JUDGE_OUT and (JUDGE_OUT / "JUDGE_GO_NO_GO.json").is_file() else None
            return self.send(200, JX.result(report, JX.coalition(), pay, go))
        if path == "/api/judge/evidence":
            name = q.get("name", "")
            if not (JUDGE_OUT and name in JUDGE_EVIDENCE and (JUDGE_OUT / name).is_file()):
                return self.send(404, {"error": "EVIDENCE_NOT_AVAILABLE", "name": name,
                                       "available": sorted(n for n in JUDGE_EVIDENCE if JUDGE_OUT and (JUDGE_OUT / n).is_file())})
            return self.send(200, (JUDGE_OUT / name).read_bytes(), "application/json" if name.endswith(".json") else "text/plain; charset=utf-8")
        return self.send(404, {"error": "not found"})

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/web/"):
                p = (WEB / u.path[5:]).resolve()
                if WEB.resolve() not in p.parents:
                    return self.send(404, {"error": "not found"})
                return self.send(200, p.read_bytes(), mimetypes.guess_type(str(p))[0] or "application/octet-stream")
            if u.path == "/api/industrial/cad027/status":
                return self.send(200, cad027_review.cad_status(CAD027))
            if u.path == "/api/industrial/cad027/stage":
                st = cad027_review.cad_status(CAD027)
                if not st["configured"]:
                    # 409 + reason + action: a client error the UI explains, never a bare 503
                    return self.send(409, {"error": "CAD_NOT_CONFIGURED", **st})
                n = int(q.get("n", "1"))
                if n not in (1, 2, 3, 4):
                    return self.send(400, {"error": "STAGE_1_TO_4"})
                return self.send(200, CAD027.stage(n))
            if u.path == "/api/industrial/cad027/report.json":
                if not (CAD027 and CAD027.report and CAD027.report.get("stage") == 4):
                    return self.send(409, {"error": "RUN_ALL_FOUR_STAGES_FIRST"})
                return self.send(200, CAD027.report, extra={"Content-Disposition": "attachment; filename=CAD027_REPORT.json"})
            if u.path.startswith("/api/judge/"):
                return self.judge_get(u.path, q)
            if u.path == "/api/industrial/ztl-gate/status":
                return self.send(200, ztl_gate.status())
            if u.path == "/api/industrial/registry":
                return self.send(200, industrial.source_registry())
            if u.path == "/api/industrial/cases":
                return self.send(200, industrial.cases_index())
            if u.path == "/api/industrial/decision":
                return self.send(200, industrial.run_case(q.get("case", "coalition")))
            if u.path == "/api/industrial/passport":
                case = q.get("case", "coalition")
                return self.send(200, industrial.run_case(case), "application/json",
                                 {"Content-Disposition": 'attachment; filename="INDUSTRIAL_PASSPORT.json"'})
            if u.path == "/api/industrial/rfq":
                case = q.get("case", "coalition")
                return self.send(200, industrial.supplier_rfq(case).encode("utf-8"), "text/plain; charset=utf-8",
                                 {"Content-Disposition": 'attachment; filename="RFQ_DRAFT_NOT_SENT.txt"'})
            if u.path == "/api/industrial/work-plan":
                return self.send(200, industrial_flow.execute_preflight_plan())
            if u.path == "/api/runs":
                return self.send(200, [{"run_id": k, "evidence_mode": json.loads((d / "DEAL_DOSSIER.json").read_text())["evidence_mode"]}
                                       for k, (_, d) in RUNS.items()])
            if u.path == "/api/dossier":
                return self.send(200, (RUNS[q["run"]][1] / "DEAL_DOSSIER.json").read_bytes())
            if u.path == "/api/download":
                name = "EXECUTION_PASSPORT.json" if q.get("kind") == "passport" else "DEAL_DOSSIER.json"
                return self.send(200, (RUNS[q["run"]][1] / name).read_bytes(), "application/json",
                                 {"Content-Disposition": f'attachment; filename="{name[:-5]}_{q["run"]}.json"'})
            if u.path == "/api/record":
                return self.send(200, {"run_id": q["run"], "ref": q["ref"], "record": resolve_ref(RUNS[q["run"]][0], q["ref"])})
            if u.path == "/api/context":
                ctx = {}
                for n in ["PAYPAL_AUTHORITY_PREFLIGHT.json", "OLD_HOLDS_RECONCILIATION_READ_ONLY.json", "LICENSE_GATE.json",
                          "COUNTERFACTUAL_A0_A1_A2_A3.json", "NEGATIVE_TESTS.json", "ECONOMIC_CASE.json"]:
                    p = EV / n
                    ctx[n] = json.loads(p.read_text()) if p.exists() else {"status": "Z", "note": "evidence file not produced"}
                return self.send(200, ctx)
            return self.send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001 - surface the error to the UI rather than crash the server
            return self.send(500, {"error": f"{type(e).__name__}: {e}", "status": "EVIDENCE UNAVAILABLE"})


def main():
    global EV, DEMO_LEDGER, CAD027, JUDGE_OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--industrial-demo-ledger", default=None, help="Optional NEW test-only intent ledger")
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--cad027-step", default=None, help="local reBot STEP (not in the repo)")
    ap.add_argument("--cad027-readme", default=None, help="local factory readme.md")
    ap.add_argument("--ztl-engineer", default=None, help="local ztl-engineer checkout (mcp_server.py)")
    ap.add_argument("--cad027-perf", default=None, help="local reBot Performance_Testing.md")
    ap.add_argument("--judge-out", default=None, help="judge_out/ directory written by scripts/judge_demo.py")
    ap.add_argument("--mode", default="replay", choices=["replay"])
    a = ap.parse_args()
    EV = Path(a.evidence).resolve()
    DEMO_LEDGER = Path(a.industrial_demo_ledger).resolve() if a.industrial_demo_ledger else None
    if a.cad027_step:
        CAD027 = cad027_review.StagedRun(a.cad027_step, a.cad027_readme, a.ztl_engineer, a.cad027_perf)
    JUDGE_OUT = Path(a.judge_out).resolve() if a.judge_out else None
    for d in sorted((EV / "dossier").iterdir()):
        dj = json.loads((d / "DEAL_DOSSIER.json").read_text())
        RUNS[dj["run_id"]] = (EV / "runs" / dj["run_dir_name"], d)
    print(json.dumps({"url": f"http://127.0.0.1:{a.port}/", "runs": list(RUNS)}), flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
