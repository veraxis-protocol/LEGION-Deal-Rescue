# Independent readback history (pay-b1)
1. 23:42:30Z (inside the run): `commerce_demo.readback` -> READBACK_MISMATCH. Cause: whole-object amount equality; PayPal's order purchase-unit amount carries an extra empty `breakdown` object while currency/value are identical (USD 99.00).
2. 23:43Z re-run before the fix was applied: READBACK_MISMATCH (same cause).
3. Diagnosis (read-only GETs): only `amount` object equality differed; status, IDs, related order, captures_on_order=1 all matched.
4. Fix: compare money as (currency_code, value) and additionally require it to equal the ledger's exact 9900 cents. 23:43:59Z re-run: VERIFIED_COMPLETED.
No POST, retry or ledger write was involved in any readback.
