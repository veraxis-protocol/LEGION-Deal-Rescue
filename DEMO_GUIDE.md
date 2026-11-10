# Demo guide (about 3 minutes)

Start the app:

```bash
python -B scripts/build_and_serve.py --evidence demo_evidence
```

Then open `http://127.0.0.1:8795/?run=run-2`.

| Step | Do | What to notice |
|---|---|---|
| 1 Lost orders | Read the five cards. Click **MOQ not met**. | Every fact opens its source record: file, record, JSON path, SHA-256. |
| 2 Opportunity | Click **Rescue these requests**. | Five buyers, a factory and an engineer. A match is not permission. A central matcher finds the same group. |
| 3 Deal & approval | Compare the three versions. Click a red **REJECT** chip. | At $540 each buyer's $108 share is over its $100 cap, so all five refuse. The cheaper design fails qualification. $495 is signed by all seven. |
| Customer offer view | Top menu. | One buyer's offer, their own signed consent and their paid $99. |
| 4 Work & verification | Click **Play**. | A replay of the recorded events. Fulfilment is simulated. The Judge passes, and the earlier failures are listed. |
| 5 Payment & outcome | Read the payer table. Click **Inspect PayPal Readback**. | Five payments, each with its consent, authorization, order, capture and readback. Fulfilment and payment are separate states. Contribution is $0: not profitable. |
| Deal Dossier / Execution Passport | Click **Download JSON**. | The complete product output. |

Switch the run selector to `run-1`: it shows no payments, because payments are bound to `run-2`'s contract.
