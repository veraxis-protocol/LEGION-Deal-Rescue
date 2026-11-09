"""Count model calls / tokens / latency recorded in a run's MODEL_DECISIONS journals (no content is read out)."""
import json
import re
from pathlib import Path


def usage(run):
    run = Path(run)
    calls, pt, ct, lat, failed = 0, 0, 0, 0.0, 0
    files = list(run.glob("owners/*/MODEL_DECISIONS.jsonl")) + [run / "MODEL_DECISIONS.jsonl"]
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)["data"]
            calls += 1
            lat += d.get("latency_s") or 0
            failed += bool(d.get("failed"))
            m = re.search(r'"prompt_tokens": (\d+)', line)
            pt += int(m.group(1)) if m else 0
            m = re.search(r'"completion_tokens": (\d+)', line)
            ct += int(m.group(1)) if m else 0
    return {"model_calls": calls, "failed_calls": failed, "prompt_tokens": pt, "completion_tokens": ct, "sum_model_latency_s": round(lat, 2),
            "nim_price_per_token": "Z (NIM endpoint; no invoice price)", "cost_usd": "Z"}
