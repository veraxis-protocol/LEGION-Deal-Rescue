"""Fetch the pinned external inputs (reBot CAD from Seeed, ZTL repositories) and verify them.

Rules: every file is checked against the manifest's size and SHA-256 before use; a cached file that no longer
matches is deleted and fetched again; a download that does not match is refused (never used). A git checkout must
resolve to the exact pinned commit.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "scripts" / "judge_manifest.json"


class SourceError(RuntimeError):
    """A pinned input could not be obtained or did not verify. Never converted into a PASS."""


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fp:
        while block := fp.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def verify_file(path: Path, spec: dict) -> dict:
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "why": "MISSING"}
    size = path.stat().st_size
    if size != spec["bytes"]:
        return {"ok": False, "why": f"SIZE_MISMATCH {size} != {spec['bytes']}"}
    digest = sha256_file(path)
    if digest != spec["sha256"]:
        return {"ok": False, "why": f"SHA256_MISMATCH {digest}"}
    return {"ok": True, "sha256": digest, "bytes": size}


def _download(url: str, dest: Path, timeout: float = 120.0) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "legion-judge-mode"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, tmp.open("wb") as fp:
            shutil.copyfileobj(r, fp, 1 << 20)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        tmp.unlink(missing_ok=True)
        raise SourceError(f"DOWNLOAD_FAILED {url}: {e}") from e
    tmp.replace(dest)


def fetch_cad(cache: Path, manifest: dict | None = None, downloader=_download) -> dict:
    """Return {name: {"path", "sha256", "bytes", "source", "cached"}} for step/readme/performance."""
    m = (manifest or load_manifest())["cad"]
    cache = Path(cache) / "cad" / m["commit"]
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, spec in m["files"].items():
        dest = cache / Path(spec["path"]).name
        check = verify_file(dest, spec)
        cached = check["ok"]
        if not cached:
            if dest.exists():
                dest.unlink()                       # tampered or stale cache entry is never reused
            url = m["raw_url"].format(commit=m["commit"], path=spec["path"])
            downloader(url, dest)
            check = verify_file(dest, spec)
            if not check["ok"]:
                bad = dest.with_suffix(dest.suffix + ".rejected")
                dest.replace(bad)
                raise SourceError(f"{name}: downloaded file rejected ({check['why']}); kept as {bad.name}")
        out[name] = {"path": str(dest), "sha256": check["sha256"], "bytes": check["bytes"], "cached": cached,
                     "source": f"{m['repository']}/blob/{m['commit']}/{spec['path']}"}
    return out


def _git(*args, cwd=None) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                              timeout=600).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        detail = getattr(e, "stderr", "") or str(e)
        raise SourceError(f"GIT_FAILED git {' '.join(args)}: {detail.strip()[-300:]}") from e


def fetch_ztl(cache: Path, manifest: dict | None = None) -> dict:
    """Clone (or reuse) ztl-engineer, ztl-stand and ZTL side by side at the pinned commits; verify HEAD."""
    m = (manifest or load_manifest())["ztl"]
    base = Path(cache) / "ztl"
    base.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, spec in m.items():
        dest = base / name
        if dest.exists():
            try:
                head = _git("rev-parse", "HEAD", cwd=dest)
            except SourceError:
                head = None
            if head != spec["commit"] or _git("status", "--porcelain", cwd=dest):
                shutil.rmtree(dest, ignore_errors=True)   # modified or wrong revision: start again
        if not dest.exists():
            _git("clone", "--quiet", "--no-checkout", spec["repository"], str(dest))
            _git("checkout", "--quiet", spec["commit"], cwd=dest)
        head = _git("rev-parse", "HEAD", cwd=dest)
        if head != spec["commit"]:
            raise SourceError(f"{name}: HEAD {head} != pinned {spec['commit']}")
        if _git("status", "--porcelain", cwd=dest):
            raise SourceError(f"{name}: working tree modified")
        out[name] = {"path": str(dest), "commit": head, "repository": spec["repository"]}
    return out
