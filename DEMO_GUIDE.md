# Demo guide (3 minutes)

Start: `python -B scripts/build_and_serve.py --evidence demo_evidence`, then open `http://127.0.0.1:8795/?run=WO004-A2-fresh-2`.

| Step | Do | What to notice |
|---|---|---|
| 1 Lost orders | Read the five cards; click **MOQ not met** | Each fact opens its source record: file, record, JSON path, SHA-256. |
| 2 Opportunity | **Rescue these requests** | 5 buyers + factory + engineer. A match is *not* permission. A3 (central matcher) finds the same group: parity. |
| 3 Deal & approval | Inspect the three versions; click a red **REJECT** chip | $540 → each buyer's $108 share is over its $100 cap, so all 5 refuse. The cheaper D-C design fails qualification. $495 is signed 7/7. |
| Customer offer view | Top menu | What one buyer sees. The PayPal button is disabled with the reason. |
| 4 Work & verification | **Play** | Replay at the recorded timestamps. All effects are SIMULATED. The independent Judge returns PASS. Earlier failed attempts are listed. |
| 5 Payment & outcome | Read | FULFILLMENT_WORLD = SIMULATED and PAYPAL = UNAUTHORIZED are separate states. $0 captured, 0/5. Contribution $0, not profitable. |
| Deal Dossier / Execution Passport | Download JSON | The full product output, with every effect, permit, receipt and denial. |
