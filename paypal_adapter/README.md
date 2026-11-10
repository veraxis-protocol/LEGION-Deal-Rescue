# PayPal Sandbox payment adapter

This adapter executes PayPal **Orders v2** payments under signed authority. It runs on Windows, and its source is
byte-identical to the one that made the five Sandbox captures (see [../docs/PAYMENT_RUNTIME.md](../docs/PAYMENT_RUNTIME.md)).

**What it guarantees**

| Area | Guarantee |
|---|---|
| Authority | Every order and capture needs all of: a current signed mission and control state, a one-time permit, and an admission attestation journaled before the POST. |
| Budget | Integer cents, a per-mission cap and a gateway-wide $500 cap. Reservations are held until the effect is resolved. |
| Idempotency | Durable request IDs. A pre-dispatch marker is written before each POST. |
| Uncertain responses | No blind retry. A timeout, a 5xx or a lost reply keeps the reservation, and a separate command reconciles read-only. |
| Buyer approval | The local callback alone is never trusted. The server must GET the order and see `APPROVED` with a payer identity before it captures. |
| Confirmation | Separate GETs of the order and the capture must match IDs, payee, effect, currency, amount and `COMPLETED`. A separate-process readback re-checks with a read-only ledger. |
| Safety stop | Contradictions in a readback set a global safety stop that is never cleared silently. |

**Credentials**
- PayPal REST credentials are read from `%LOCALAPPDATA%\Veraxis\LEGION-Commerce\`, sealed with Windows DPAPI.
- The adapter never imports credentials from the environment, the repository or the browser.

**Tests (no network, fake provider; Windows, because the adapter uses Windows DPAPI)**

```bash
pip install -r requirements.lock
python -B -m unittest discover -s tests -t .
```

The suite has 46 tests, including `tests/test_release_negatives.py`. It covers:
- payee swap and approval without a payer identity (N10);
- capture without provider approval (N14);
- duplicate capture (N07).

**Interface.** The signed envelope formats (acceptance, mission, permit, control) are specified in
[docs/ADMISSION_INTERFACE.md](docs/ADMISSION_INTERFACE.md).

**History.** [docs/ORIGINAL_README.md](docs/ORIGINAL_README.md) is the adapter's original README from its first release,
kept as written under a dated header.
