"""Judge Mode offline tests: pinned-source verification, case separation, verdict logic, CAD status (no 503)."""
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from deal_rescue import server
from deal_rescue.industrial import cad027_review as R
from deal_rescue.judge import passport as P, sources as S

ROOT = Path(__file__).resolve().parents[1]


def mini_manifest(data: bytes) -> dict:
    return {"cad": {"repository": "https://example.invalid/repo", "commit": "c" * 40, "raw_url": "x://{commit}/{path}",
                    "files": {"step": {"path": "a/b.step", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}}


class Sources(unittest.TestCase):
    def test_manifest_pins_everything(self):
        m = S.load_manifest()
        for spec in m["cad"]["files"].values():
            self.assertEqual(len(spec["sha256"]), 64)
            self.assertGreater(spec["bytes"], 0)
        self.assertEqual(m["cad"]["files"]["step"]["sha256"], R.PINNED_STEP_SHA256)
        self.assertEqual(len(m["cad"]["commit"]), 40)
        for spec in m["ztl"].values():
            self.assertEqual(len(spec["commit"]), 40)

    def test_wrong_download_is_refused(self):
        good = b"ISO-10303-21;\n"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(S.SourceError):
                S.fetch_cad(Path(d), mini_manifest(good), downloader=lambda url, dest: dest.write_bytes(b"EVIL" * 4))

    def test_tampered_cache_is_refetched_not_used(self):
        good = b"ISO-10303-21;\nEND;\n"
        calls = []
        with tempfile.TemporaryDirectory() as d:
            dl = lambda url, dest: (calls.append(url), dest.write_bytes(good))
            first = S.fetch_cad(Path(d), mini_manifest(good), downloader=dl)
            Path(first["step"]["path"]).write_bytes(b"tampered!!!!!!!!!!")
            second = S.fetch_cad(Path(d), mini_manifest(good), downloader=dl)
            self.assertEqual(len(calls), 2)
            self.assertFalse(second["step"]["cached"])
            self.assertEqual(Path(second["step"]["path"]).read_bytes(), good)

    def test_unreachable_source_is_explicit(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(S.SourceError):
            S._download("http://127.0.0.1:9/x", Path(d) / "x", timeout=5)


class Cases(unittest.TestCase):
    def setUp(self):
        d = json.loads((ROOT / "demo_evidence/dossier/run-2/DEAL_DOSSIER.json").read_text(encoding="utf-8"))
        self.slots = d["paypal"]["slots"]
        self.h = self.slots[0]["contract_hash"]

    def test_captures_bind_to_their_own_contract(self):
        out = P.bind_payments(self.h, self.slots)
        self.assertEqual((len(out["captures"]), out["provider_confirmed_cents"]), (5, 49500))

    def test_mixed_contract_hashes_refused(self):
        mixed = [dict(s) for s in self.slots]
        mixed[2]["contract_hash"] = "f" * 64
        with self.assertRaises(P.BindingError):
            P.bind_payments(self.h, mixed)

    def test_historic_capture_never_moves_to_cad_case(self):
        a = P.case_a_contract_hash(R.PINNED_STEP_SHA256, "b" * 64, "c" * 64)
        self.assertNotEqual(a, self.h)
        with self.assertRaises(P.BindingError):
            P.bind_payments(a, self.slots)


class Verdict(unittest.TestCase):
    def test_skip_makes_final_F(self):
        g = {k: "T" for k in P.REQUIRED}
        self.assertEqual(P.final_verdict(g, 0), "T")
        self.assertEqual(P.final_verdict(g, 1), "F")
        self.assertEqual(P.final_verdict({**g, "browser_e2e": "Z"}, 0), "Z")
        self.assertEqual(P.final_verdict({**g, "bom": "F"}, 0), "F")

    def test_stale_evidence_detected(self):
        cur = {"git_commit": "a", "cad_sha256": "b", "source_manifest_sha256": "c", "bom_digest": "d", "requirements_digest": "e"}
        self.assertEqual(P.verify_against(cur, cur), [])
        self.assertEqual(P.verify_against({**cur, "bom_digest": "x"}, cur), ["bom_digest"])


class Timeline(unittest.TestCase):
    """started_utc <= preflight_finished_utc <= browser_e2e_finished_utc <= finished_utc; final=T only after all."""

    def doc(self, **kw):
        d = {"gates": {k: "T" for k in P.REQUIRED}, "skipped_required": 0, "started_utc": "2026-11-12T17:00:00+00:00",
             "preflight_finished_utc": "2026-11-12T17:02:00+00:00", "browser_e2e_finished_utc": None, "finished_utc": None}
        d["gates"]["browser_e2e"] = "Z"
        d.update(kw)
        return d

    def browser(self, verdict="T", finished="2026-11-12T17:03:00+00:00"):
        return {"verdict": verdict, "checks": "42/42", "console_errors": 0, "failed_requests": 0, "screenshots": 14,
                "finished_utc": finished}

    def test_ordered_timeline_allows_T(self):
        d = P.finalize(self.doc(), self.browser(), "2026-11-12T17:03:05+00:00")
        self.assertTrue(d["timeline"]["ok"])
        self.assertEqual(d["final"], "T")
        self.assertEqual(d["finished_utc"], "2026-11-12T17:03:05+00:00")

    def test_preflight_alone_is_never_T(self):
        d = self.doc()
        self.assertFalse(P.check_timeline(d)["ok"])          # no browser / finished time yet
        self.assertEqual(P.final_verdict(d["gates"], 0), "Z")

    def test_finished_before_browser_blocks_go(self):
        d = P.finalize(self.doc(), self.browser(finished="2026-11-12T17:03:00+00:00"), "2026-11-12T17:02:30+00:00")
        self.assertEqual((d["timeline"]["ok"], d["final"]), (False, "F"))
        self.assertIn("ORDER", d["timeline"]["why"])

    def test_browser_before_preflight_blocks_go(self):
        d = P.finalize(self.doc(), self.browser(finished="2026-11-12T17:01:00+00:00"), "2026-11-12T17:03:05+00:00")
        self.assertEqual(d["final"], "F")

    def test_missing_timestamp_blocks_go(self):
        d = P.finalize(self.doc(preflight_finished_utc=None), self.browser(), "2026-11-12T17:03:05+00:00")
        self.assertEqual((d["final"], d["timeline"]["why"]), ("F", "MISSING preflight_finished_utc"))

    def test_failed_browser_is_not_T_even_when_ordered(self):
        d = P.finalize(self.doc(), self.browser("F"), "2026-11-12T17:03:05+00:00")
        self.assertTrue(d["timeline"]["ok"])
        self.assertEqual(d["final"], "F")


class CadStatus(unittest.TestCase):
    def test_unconfigured_is_explained(self):
        s = R.cad_status(None)
        self.assertFalse(s["configured"])
        self.assertIn("judge_demo", s["action"])

    def test_missing_file_is_explained(self):
        run = R.StagedRun(Path("/nonexistent/x.step"), Path("/nonexistent/readme.md"), None)
        s = R.cad_status(run)
        self.assertEqual((s["configured"], s["reason"].split(":")[0]), (False, "CAD_INPUT_MISSING"))

    def test_server_never_answers_503_for_cad(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        old = server.CAD027
        server.CAD027 = None
        try:
            base = f"http://127.0.0.1:{httpd.server_port}"
            st = json.loads(urllib.request.urlopen(base + "/api/industrial/cad027/status").read())
            self.assertFalse(st["configured"])
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(base + "/api/industrial/cad027/stage?n=1")
            self.assertEqual(cm.exception.code, 409)
            body = json.loads(cm.exception.read())
            self.assertEqual(body["error"], "CAD_NOT_CONFIGURED")
            self.assertTrue(body["action"])
            js = json.loads(urllib.request.urlopen(base + "/api/judge/state").read())
            self.assertFalse(js["cad"]["configured"])
        finally:
            server.CAD027 = old
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
