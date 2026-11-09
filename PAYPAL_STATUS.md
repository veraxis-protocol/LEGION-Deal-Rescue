# PayPal integration status (2026-11-09 23:44Z)

**`PAYPAL_PARTIAL_GO (1/5)` — one genuine PayPal Sandbox payment, independently confirmed.**

| Payer | State | Evidence |
|---|---|---|
| Customer A (`owner:b1`) | **SANDBOX_PAYMENT_CONFIRMED $99.00** — order `21U22496GM957054P` COMPLETED, capture `0DR81708WC9477605` COMPLETED, USD 99.00, final, 1 capture on the order | `demo_evidence/paypal_runs/lmf007-20261109T232734Z/` |
| Customers B–E | NOT_AUTHORIZED — no order exists | — |

**How b1 was paid (sandbox-demo-v1 profile, `LEGION-Commerce/commerce_demo` + A04 gateway):**
1. Mission `LMF-007-20261109T232734Z` drafted for one payer, bound to the seven-owner contract `809b4f82…` (fresh run 2, Judge PASS 63/63) and to b1's OWN signed ACCEPT `commit-59268f25…` (max 9,900 cents).
2. Owner signed mission + control with the Control Key (passphrase-gated); verified before run (mission hash `b6e8ab89…`, identical to draft).
3. Fresh qualified Lean decision **T** for the exact action; journaled `LEAN_ATTESTED` before each POST.
4. One order create (HTTP 200, `PAYER_ACTION_REQUIRED`) → buyer approved on PayPal's own page (one earlier visit returned via *cancel*; no effect) → server GET `APPROVED` → one capture POST (HTTP 201) → GETs: order `COMPLETED`, capture `COMPLETED` 9,900.
5. Independent readback in a separate process (read-only ledger, fresh GETs): `VERIFIED_COMPLETED`. Its first two runs failed with `READBACK_MISMATCH` because PayPal's purchase-unit amount carries an extra empty `breakdown` object; the check now compares (currency, value) and the exact ledger cents. History: `READBACK_HISTORY.md`.
6. Ledger: 1 effect, **2 POSTs total (create + capture), 0 retries, 0 duplicate captures**.

**Controls (mechanism, fake provider):** payment negatives 6/6 (over-cap, duplicate effect, changed amount, wrong payer, stale epoch, missing consent), adapter suite 42/42 (revoked/expired permit, lost capture reply, callback without APPROVED, duplicate capture).

**Not claimed:** production admission (independent A03 acceptance is still unsigned; the Sandbox profile deliberately uses separate signature domains), real money, physical delivery, or payment for b2–b5. A mission draft for b2–b5 (`LMF-007-20261109T234414Z`, 4 × $99, each bound to that buyer's own consent) awaits the owner's signature; each buyer approves separately.

**Historic 2026-11-07 orders** (different contract, paused run): 4 held, never approved, 0 captured; untouched.

**Adapter build note:** `paypal_adapter/` here is A04 `ff6dcd1`. The payment above ran on LEGION-Commerce `61dd814`+ (same adapter plus mandatory Lean attestation before each POST; `gateway.py` differs), which is also the build the unsigned A03 v5 request covers.
