# PayPal payments

**Status: all five buyers paid in PayPal Sandbox — $495.00, each payment independently confirmed.**
Sandbox amounts are test money, not revenue.

| Customer | Buyer consent | Order | Capture | Result |
|---|---|---|---|---|
| A | `commit-59268f254f1c46e3` | `21U22496GM957054P` | `0DR81708WC9477605` | COMPLETED · USD 99.00 |
| B | `commit-9ef8a556c27c48a3` | `94R14114MG3843349` | `76276237BR937351W` | COMPLETED · USD 99.00 |
| C | `commit-d332f282a3084f94` | `9JC70580TU2910239` | `71988721JR129760J` | COMPLETED · USD 99.00 |
| D | `commit-c46aee2c5f2a4e7d` | `87755191MF0805623` | `3PG41022DY609720J` | COMPLETED · USD 99.00 |
| E | `commit-5fdb43cd6853409c` | `5AM5115112156543W` | `65542700KX1483810` | COMPLETED · USD 99.00 |

- **When:** 2026-11-09 23:42Z to 2026-11-10 00:05Z.
- **Contract:** all five payments are bound to the seven-party contract `809b4f82b5bd3e3dd130d98ae3ca9644d7bca77818b60284e8d3ac0d9763dc8d` (`run-2`).
- **Totals:** 5 orders, 5 captures, **10 POSTs (one create and one capture per buyer), 0 retries, 0 duplicate captures**.
- **Evidence:** `demo_evidence/paypal_runs/`. Merchant ID and payer identity are redacted; order and capture IDs are kept so they can be checked.

## How a payment is made

1. **Consent.** Each buyer's line is bound to that buyer's own signed acceptance of the final contract for exactly 9,900 cents. No buyer's consent is reused for another.
2. **Authorization.** The platform operator signs a payment authorization with its control key, which is passphrase-protected. Customer A was authorized alone first; then B to E were authorized together, one line per buyer.
3. **Admission.** Before each PayPal POST, a fresh admission decision for the exact payer, amount and merchant must return T. It is journaled before the call, and a one-time permit is issued.
4. **Order.** One order per buyer (Orders v2, intent CAPTURE, effect ID as `invoice_id`).
5. **Buyer approval.** The buyer approves on PayPal's own page. The return to the local callback is not trusted on its own: the server must GET the order and see `APPROVED` with a payer identity.
6. **Capture.** Exactly one capture POST, confirmed by GETs of the order and the capture.
7. **Independent readback.** A separate process with a read-only ledger and fresh GETs checks:
   - the order and capture IDs;
   - status `COMPLETED`;
   - amount USD 99.00;
   - a single capture on the order;
   - that the capture links to its order and effect.

   It then reports `VERIFIED_COMPLETED`.
8. **Display.** The app marks a payment as confirmed only when the readback, the payment ledger and the event journal all agree, and the authorization is bound to the same contract hash as the run.

## A failure along the way, kept as evidence

The first readback for Customer A failed with `READBACK_MISMATCH`. PayPal returns the order amount with an extra, empty
`breakdown` object, so comparing whole objects failed even though currency and value matched.

The readback now compares currency and value, plus the exact cents in the ledger, and it was re-run read-only. Customers B
to E used the corrected readback. History: `demo_evidence/paypal_runs/lmf007-20261109T232734Z/READBACK_HISTORY.md`.

## Controls

| Control | Result |
|---|---|
| Adapter test suite (fake provider, real SQLite, crash cases) | 46/46 |
| Payment negative controls, `scripts/run_payment_negatives.py` | All pass. Covered: duplicate capture, lost capture response, payee swap at the provider, approval without payer identity, capture without provider approval, forged or unapproved callback |
| Over-cap payment, changed amount, wrong payer, stale epoch, missing consent | 6/6 rejected, 0 POSTs (orchestration negatives, LEGION-Commerce) |
| Live payments | No duplicate capture; no capture without buyer approval |

## Limits

- **Sandbox only.** No real money moved.
- **Production.** Production payments additionally require an independent review and acceptance of the payment adapter, which has not been signed. The Sandbox authorization used here has its own signature domains and does not claim production admission.
- **Payee.** The payee is a PayPal Sandbox business account. A real merchant of record is not established.
- **Earlier orders.** Four orders created on 2026-11-07 for an earlier contract were never approved or captured. Their reservations remain held in that run's ledger and were left untouched.
