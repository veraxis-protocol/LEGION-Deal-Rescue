# LEGION Deal Rescue

**Turn customer requests you cannot fulfill into verified business opportunities.**
Find partners. Agree on terms. Verify delivery. Get paid with PayPal when each buyer authorizes it.

Entry for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/rules) · License: **Apache-2.0** (this repository) — see [Licensing](#licensing-read-this) for the external PolyForm-Noncommercial dependencies.

> **Status, stated plainly (2026-11-09):**
> - The AI-driven seven-owner deal formation, contract versioning and independent Judge **run end to end** (two fresh first attempts, both Judge `PASS_COMPLETED`, 63/63 checks).
> - The deal is a **synthetic scenario**: buyers, factory, engineer, manufacture, shipment and buyer-ledger payments are **SIMULATED**.
> - **PayPal: one real Sandbox payment confirmed — `PAYPAL_PARTIAL_GO (1/5)`.** On 2026-11-09 Customer A's own Sandbox buyer approved $99.00 on PayPal; order `21U22496GM957054P` was captured once (capture `0DR81708WC9477605`, COMPLETED, USD 99.00) under an owner-signed mission bound to the seven-owner contract, and a separate-process readback of PayPal's records verified it. The other four payers are not yet authorized (each needs its own signed mission line and buyer approval). Sandbox = test money, not real revenue. See [`PAYPAL_STATUS.md`](PAYPAL_STATUS.md).
> - Economics: the scenario's $495 price equals its $495 vendor cost → **contribution $0 before overhead; not profitable**.

## What it does

A small merchant receives five requests for 20 sensor modules each (max $100 per customer). The factory's minimum order is 100, so each request alone is refused. LEGION:

1. **Discovers** compatible demand on a marketplace where each of seven independent owners (5 buyers, 1 manufacturer, 1 qualification engineer) publishes only what it chooses to share.
2. **Negotiates** one 100-unit contract across seven owner processes, each with its own key, private policy and NVIDIA NIM model agent. Every price change creates a new contract version that needs fresh signatures.
   - v1 $480 → invalidated by an **injected test** price shock.
   - v2 $540 = $108/buyer → **denied by all five buyers** (each above its own $100 cap).
   - A cheaper design ($380) **fails the independent engineer** and is never offered.
   - v3 $495 = $99/buyer → signed by all seven.
3. **Executes** in each owner's simulated world (manufacture, certification, 5 shipments, 5 ledger payments) with signed receipts.
4. **Verifies** with an independent, read-only Judge that reads every owner's live state, plus 4 tamper mutants and 25 adversarial negatives.
5. **Pays** each buyer's own $99 line through PayPal **only** when that buyer approves on PayPal and the owner's authority checks pass. Currently: 1 of 5 paid and independently verified (Sandbox).

The merchant UI has five screens (Lost orders · Opportunity · Deal & approval · Work & verification · Payment & outcome), a customer offer view, a downloadable **Deal Dossier** and an **Execution Passport**. Every number links to the exact retained record (file, sequence/line, JSON path, record hash, file SHA-256).

## Quick start (no secrets; Windows, macOS or Linux; Python 3.11+)

```bash
git clone https://github.com/veraxis-protocol/LEGION-Deal-Rescue.git
cd LEGION-Deal-Rescue
python -B scripts/build_and_serve.py --evidence demo_evidence
# open http://127.0.0.1:8795/?run=WO004-A2-fresh-2
```

This mode **replays two real fresh runs** recorded on 2026-11-09 (`demo_evidence/runs/`). It rebuilds every dossier from the raw journals and re-audits them. It is labelled *replay* in the UI. It makes no model or PayPal calls.

## Full live run (fresh AI execution)

`scripts/run_live_e2e.ps1` runs a **new** seven-owner episode with real NVIDIA NIM decisions and the independent Judge. It needs:
- Windows PowerShell;
- git and Python 3.11+;
- network access to GitHub and `integrate.api.nvidia.com`;
- your own NVIDIA NIM API key in a local file (never committed).

```powershell
.\scripts\run_live_e2e.ps1 -NimKeyFile C:\path\to\nvapi.txt
```

It clones the PolyForm-Noncommercial LEGION dependencies at pinned commits into `external/`, then:
1. verifies the Judge source hash;
2. runs the episode;
3. runs the 25 negatives;
4. builds, audits and serves the result.

Details: [`REPRODUCE.md`](REPRODUCE.md).

## Tests

```bash
python -B -m unittest discover -s tests -v                                     # app release tests (5)
cd paypal_adapter && python -B -m unittest discover -s tests -t .             # PayPal adapter mechanism tests (42; needs cryptography)
```

## Repository layout

| Path | What | License |
|---|---|---|
| `deal_rescue/` | Dossier builder, read-only server, merchant UI, UI-evidence auditor, economic case | Apache-2.0 |
| `paypal_adapter/` | PayPal Sandbox Orders v2 gateway with durable safety gates. Copied verbatim from `LEGION-Commerce@ff6dcd1` (WO-COM-A04); `A04_README.md` is its original README. | Apache-2.0 (owner decision 2026-11-09) |
| `scripts/` | Replay builder/server, live E2E launcher | Apache-2.0 |
| `tests/` | Release acceptance tests | Apache-2.0 |
| `demo_evidence/` | Two fresh run records (redacted: owner-private configs and journals excluded), negative-suite results, gate readings | Apache-2.0 (data) |
| `external/` (not in git) | LEGION Core, LEGION-Federation, LEGION-Marketplace at pinned commits | **PolyForm Noncommercial 1.0.0** |

## Licensing (read this)

- **This repository is Apache-2.0.** It contains the complete Deal Rescue application, the PayPal adapter, the integration interfaces, the launchers, tests and docs.
- **The live seven-owner run depends on three external projects**: [LEGION](https://github.com/veraxis-protocol/LEGION) (Core), [LEGION-Federation](https://github.com/veraxis-protocol/LEGION-Federation) and [LEGION-Marketplace](https://github.com/veraxis-protocol/LEGION-Marketplace). These remain under **PolyForm Noncommercial 1.0.0**. They are not copied, modified or relicensed here; the launcher fetches them at pinned commits. Commercial use of those components requires a separate agreement with Veraxis.
- Replay mode, the UI, the auditor, the tests and the PayPal adapter run without them.
- **Organizer acceptance of this dependency structure has not been obtained** (no ruling on file).

See [`NOTICE`](NOTICE) and [`PROVENANCE_AND_LICENSE.md`](PROVENANCE_AND_LICENSE.md).

## Honest limits

- Synthetic scenario, not real customers.
- No physical goods.
- PayPal: 1 of 5 payers captured in Sandbox (test money); 4 not yet authorized.
- No profit at the frozen prices.
- A central matcher with the same public data finds the same coalition: we claim **no matching advantage**. The difference is per-owner signed consent, private terms, admission checks and independent verification.
- No unaided user study has been run.

Full list: [`CHALLENGES_AND_LIMITS.md`](CHALLENGES_AND_LIMITS.md).
