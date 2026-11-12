# Demo guide

## Judge walkthrough (about 5 minutes)

```bash
python -m scripts.judge_demo
```

The app opens at `http://127.0.0.1:8801/#judge=1`. You can also click **Judge walkthrough · drawing to payment**.

| Step | Case | What to notice |
|---|---|---|
| 1 Drawing | A (real) | The reBot STEP's SHA-256 matches the pinned Seeed source. The readme and performance doc hashes are listed. |
| 2 Parts | A (real) | XCAF is computed now: 33 sub-assemblies, 64 part definitions and 326 instances. The factory BOM matches 40/40 parts and 53/53 instances. Pick a part for procurement. |
| 3 Engineering review | A (real) | Each reBot predicate shows its source lines and its missing data. The verdict is **OPEN** with `RAIL_TOLERANCE` **Z**. A dashed box shows a ZTL integration test that is **not a reBot check**. CAD-025 gives ENGINEERING_ADMISSION **Z**. |
| 4 Procurement | A (real) | The fields a supplier request needs, with confirmed and missing ones marked. Status is **BLOCKED** until engineering admission. The RFQ is a draft, not sent, with no CAD attached. |
| 5 Coalition | synthetic | Five requests of 20 make 100/100 units, with each buyer's all-in cost against its cap. Computed now from clearly synthetic fixtures. |
| 6 Payment | B (recorded) | The $480 → $540 → $495 contract versions, the independent Judge's 63/63 checks, and five PayPal Sandbox order and capture IDs on one contract. |
| 7 Result | A + B | The execution passport. CASE B's captures are **refused** for CASE A. The gates that would connect A to B are listed, along with the boundaries and links to every evidence file. |

Open a single step directly with `/#judge=N`.

## Recorded seven-party run (about 3 minutes)

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
