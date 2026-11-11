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
from deal_rescue.industrial import core as industrial, workflow as industrial_flow, demo_intent, cad_bom
from urllib.parse import parse_qs, urlparse

WEB = Path(__file__).parent / "web"
EV = None
DEMO_SESSIONS = {}
DEMO_LEDGER = None
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
        if u.path not in ("/api/industrial/intake", "/api/industrial/engineering-extract", "/api/industrial/demo-confirm"):
            return self.send(405, {"error":"METHOD_NOT_ALLOWED"})
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self.send(415, {"error":"JSON_ONLY"})
        origin=self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:"+str(self.server.server_port),
                                    "http://localhost:"+str(self.server.server_port)):
            return self.send(403, {"error":"CROSS_ORIGIN_POST_DENIED"})
        try:
            size=int(self.headers.get("Content-Length", "-1"))
            limit=23000000 if u.path in ("/api/industrial/engineering-extract","/api/industrial/intake") else 2900000
            if not 0<size<=limit: return self.send(413,{"error":"REQUEST_TOO_LARGE"})
            self.connection.settimeout(10)
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):return self.send(400,{"error":"OBJECT_EXPECTED"})
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
    global EV, DEMO_LEDGER
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--industrial-demo-ledger", default=None, help="Optional NEW test-only intent ledger")
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--mode", default="replay", choices=["replay"])
    a = ap.parse_args()
    EV = Path(a.evidence).resolve()
    DEMO_LEDGER = Path(a.industrial_demo_ledger).resolve() if a.industrial_demo_ledger else None
    for d in sorted((EV / "dossier").iterdir()):
        dj = json.loads((d / "DEAL_DOSSIER.json").read_text())
        RUNS[dj["run_id"]] = (EV / "runs" / dj["run_dir_name"], d)
    print(json.dumps({"url": f"http://127.0.0.1:{a.port}/", "runs": list(RUNS)}), flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
