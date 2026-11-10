# PayPal integration status (2026-11-10 00:05Z)

**`PAYPAL_PAYMENT_GO (5/5)` — five genuine PayPal Sandbox payments, each approved by its own buyer and independently confirmed. $495.00 (Sandbox test money).**

| Payer | Order | Capture | Status | Mission |
|---|---|---|---|---|
| Customer A `owner:b1` | `21U22496GM957054P` | `0DR81708WC9477605` | COMPLETED, USD 99.00 | `LMF-007-20261109T232734Z` |
| Customer B `owner:b2` | `94R14114MG3843349` | `76276237BR937351W` | COMPLETED, USD 99.00 | `LMF-007-20261109T234414Z` |
| Customer C `owner:b3` | `9JC70580TU2910239` | `71988721JR129760J` | COMPLETED, USD 99.00 | `LMF-007-20261109T234414Z` |
| Customer D `owner:b4` | `87755191MF0805623` | `3PG41022DY609720J` | COMPLETED, USD 99.00 | `LMF-007-20261109T234414Z` |
| Customer E `owner:b5` | `5AM5115112156543W` | `65542700KX1483810` | COMPLETED, USD 99.00 | `LMF-007-20261109T234414Z` |

Evidence: `demo_evidence/paypal_runs/` (merchant id redacted; ledger exports, events, per-payer readbacks).

**How each payment was made (sandbox-demo-v1 profile, LEGION-Commerce `commerce_demo` + A04 gateway):**
1. Mission drafted from the seven-owner contract `809b4f82…` (fresh run 2, Judge PASS 63/63); each payer line bound to that buyer's OWN signed ACCEPT commitment for exactly 9,900 cents (5 distinct commitments).
2. Owner signed mission + control with the Control Key (passphrase-gated); signature and draft identity verified before each run.
3. Per payer: fresh qualified Lean decision **T**, journaled before each POST → one order create → that buyer approves on PayPal's own page → server GET `APPROVED` → one capture POST → GETs `COMPLETED` → independent separate-process readback `VERIFIED_COMPLETED`.
4. Ledgers: b1 run 2 POSTs / 1 effect; b2–b5 run 8 POSTs / 4 effects. **0 retries, 0 duplicate captures, 0 forbidden effects.** Budget never exceeded the signed cap ($99 and $396).
5. The first b1 readback failed (`READBACK_MISMATCH`, an extra empty `breakdown` object in PayPal's order amount); fixed to compare (currency, value) + exact ledger cents before b2–b5 ran. History: `paypal_runs/lmf007-20261109T232734Z/READBACK_HISTORY.md`.

**Controls (mechanism, fake provider):** payment negatives 6/6 (over-cap 6th payment, duplicate effect, changed amount, wrong payer, stale epoch, missing consent), adapter suite 42/42 (revoked/expired permit, lost capture reply, callback without APPROVED, duplicate capture).

**Not claimed:** real money or real TPV; production admission (independent A03 acceptance is unsigned; the Sandbox profile uses separate signature domains); physical delivery (still SIMULATED); merchant profit ($495 receipts = $495 cost).

**Historic 2026-11-07 orders** (different contract, paused run): 4 held, never approved, 0 captured; untouched.

**Adapter build note:** `paypal_adapter/` here is A04 `ff6dcd1`. The payments ran on LEGION-Commerce `61dd814`+ (same adapter plus mandatory Lean attestation before each POST; `gateway.py` differs) with the readback fix `0bb385f`.
