# PayPal integration status (truthful, 2026-11-09)

| Item | State | Evidence |
|---|---|---|
| Adapter code (Orders v2: create → buyer approval → server GET APPROVED → capture → separate-process readback) | Present: `paypal_adapter/` | `paypal_adapter/A04_README.md`, `paypal_adapter/docs/ADMISSION_INTERFACE.md` |
| Adapter mechanism tests (fake provider, real SQLite, crash cases) | **42/42 PASS** | `python -m unittest discover -s tests -t .` in `paypal_adapter/` |
| Native Sandbox payment in this release | **NOT RUN: 0 orders created, 0 approvals, 0 captures, $0** | `demo_evidence/PAYPAL_AUTHORITY_PREFLIGHT.json` |
| Historic Sandbox attempt (2026-11-07, earlier run, different contract) | 4 orders created, buyer approval never given, 0 captures; 4 reservations still held in the local ledger | `demo_evidence/OLD_HOLDS_RECONCILIATION_READ_ONLY.json` (order IDs masked) |

**Why no payment was taken.** The adapter refuses to create an order unless all eight admission checks are true. The checks that are still F or Z, and who must act:

| Check | State | Who must act |
|---|---|---|
| Independent signed A03 acceptance of the exact adapter source | missing | Independent acceptor |
| A current owner-signed mission, control and per-buyer one-time permit for this contract | missing | Owner |
| Lifting the owner's pause | pause active | Owner |
| Reconciling the 4 historic holds | 4 still held | Owner |
| Identified merchant of record | not identified | Owner |
| Real Sandbox buyer approval for each payer | none | Each buyer |

None of these can be produced by the developer, and none is bypassed.

**Note on the earlier pin mismatch.** The local A04 checkout was at `4c7e6b7` while the published pin is `ff6dcd1`. The two differ only in one README line; the `commerce_adapter` runtime is byte-identical.

**What would change this.** All of the following, in order:
1. A03 accepted by an independent party for this source.
2. Owner-signed authority installed under `%LOCALAPPDATA%\Veraxis\LEGION-Commerce\a04\`.
3. The pause lifted.
4. Each Sandbox buyer approves on PayPal's page.
5. Run `create` → `serve-approval` → `capture` → `independent-readback`.

One approved $99 capture would prove a **partial (1/5)** native payment. It would not complete the five-payer deal.
