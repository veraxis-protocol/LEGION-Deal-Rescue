# LEGION Deal Rescue

**Turn customer requests you cannot fulfil into verified deals — and get paid through PayPal only when each buyer approves.**

Apache-2.0 · Entry for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/rules)

---

## 1. The problem

Small merchants turn away custom orders every day. A request is often too small for a supplier's minimum order, or it
needs an independent check nobody can arrange. Several such requests could be served together, but pooling strangers'
orders needs trust: who agreed to what, whose budget limit applies, who verified the work, and that nobody is charged
without consent.

## 2. The product

LEGION Deal Rescue is a merchant workspace that turns individually impossible requests into one verifiable collective
deal. Seven independent parties (five buyers, a manufacturer, a qualification engineer) each run their own process with
their own key, private policy and AI agent.

1. **Lost orders.** Five requests for 20 sensor modules each, at most $100 per customer. The factory's minimum order is 100 units, so each request alone is refused.
2. **Opportunity.** A marketplace sees only what each party chose to publish and finds that the five requests together reach 100 units. A match is not permission.
3. **Deal & approval.** Every price change creates a new contract version that each party must sign.
   - $480 is invalidated by a price shock (an injected test event).
   - $540, which is $108 per buyer, is refused by all five buyers because it is above each buyer's own cap.
   - A cheaper design fails the engineer's qualification and is never offered.
   - **$495, which is $99 per buyer**, is signed by all seven.
4. **Work & verification.** Manufacture, certification, five shipments and five ledger entries are replayed from the recorded events. An independent, read-only Judge reads every party's state and returns its verdict.
5. **Payment & outcome.** Each buyer pays its own $99 through PayPal. Fulfilment state and payment state are shown separately, and every payment links to PayPal's own records.

The app also has a customer offer view and a downloadable **Deal Dossier** and **Execution Passport**. Every number on
screen links to the exact record it came from: file, record, JSON path and SHA-256.

## 3. Demonstrated result

| What | Result | Evidence |
|---|---|---|
| Seven-party deal, fresh runs (each a first attempt) | **4 of 4** passed the independent Judge, **63/63 checks** each, 4/4 tamper tests detected | `demo_evidence/runs/`, [VERIFICATION.md](VERIFICATION.md) |
| Price above caps ($540) | refused by 5 of 5 buyers on their own cap rule | contract versions in each run |
| Incompatible cheaper design | rejected by the engineer, never offered | qualification records |
| Adversarial negatives against live parties | **25/25**, 0 forbidden effects | `demo_evidence/negatives/` |
| **PayPal Sandbox payments** | **5 of 5 buyers paid, $495.00**: 5 orders, 5 captures, each confirmed by an independent readback; 10 POSTs, 0 retries, 0 duplicate captures | [PAYPAL_STATUS.md](PAYPAL_STATUS.md), `demo_evidence/paypal_runs/` |

**What is not claimed:**
- PayPal amounts are **Sandbox test money**, not revenue.
- Manufacture, shipping and buyer-ledger entries are **simulated**.
- The deal is **not profitable**: buyers pay $495 and the costs are $495.
- Production payment acceptance (an independent review of the payment adapter) is **not signed**.

See [CHALLENGES_AND_LIMITS.md](CHALLENGES_AND_LIMITS.md).

## 4. PayPal integration

Each buyer's $99 is a separate PayPal **Orders v2** payment. Every link in the chain below is read from retained evidence:

`contract → buyer's own signed consent → operator-signed payment authorization + one-time permit → admission decision → order → buyer approval on PayPal → server check of APPROVED → capture → independent readback`

The payment adapter keeps:
- durable reservations;
- idempotent request IDs;
- no blind retry after an uncertain response.

It captures only after PayPal itself reports the buyer's approval. A second process re-reads PayPal's records before the app shows a payment as confirmed.

Details: [PAYPAL_STATUS.md](PAYPAL_STATUS.md). The exact code that made the five captures: [docs/PAYMENT_RUNTIME.md](docs/PAYMENT_RUNTIME.md).

## 5. Architecture

| Layer | Component | Where |
|---|---|---|
| Parties | 7 party processes (key, private policy, simulated world, NVIDIA NIM agent) | LEGION-Federation (external) |
| Discovery & harness | intent publication, matching, end-to-end run, independent Judge | LEGION-Marketplace (external) |
| Runtime | LEGION Core worlds and admission | LEGION (external) |
| Payments | PayPal Orders v2 gateway | `paypal_adapter/` (this repo) |
| Payment orchestration | per-payer authorization, admission, readback | LEGION-Commerce (external, by commit and hash) |
| Merchant app | dossier builder, read-only server, UI, evidence auditor, economics | `deal_rescue/` (this repo) |

Full dependency map with revisions and licenses: [docs/DEPENDENCY_MAP.md](docs/DEPENDENCY_MAP.md).

### Industrial Sourcing (preview)

The header button **Industrial Sourcing** opens a read-only panel that applies the same approach to manufactured parts:

- buyer requests are grouped only when the specification digest, revision, process and material match exactly;
- four routes are compared: direct purchase, single additive build, split supply and collective procurement;
- the result is a Federation **proposal** (not an admitted contract), an evidence passport and an **unsent** draft RFQ.

It ships three synthetic scenarios (coalition chosen at $2,300 vs $3,850 direct; direct chosen when it costs $2,000; a revision mismatch that leaves 80 of the required 100 units and is held). Supplier entries are 87 public discovery links, not quotations. Engineering verification stays unproven until an independent ZTL Engineering receipt is supplied. No supplier is contacted and no payment is made. Details: [docs/INDUSTRIAL_SOURCING.md](docs/INDUSTRIAL_SOURCING.md).

## 6. Installation and use

**A. Explore the recorded runs.** Any OS, Python 3.11+, no credentials.

```bash
git clone https://github.com/veraxis-protocol/LEGION-Deal-Rescue.git
cd LEGION-Deal-Rescue
python -B scripts/build_and_serve.py --evidence demo_evidence
# open http://127.0.0.1:8795/?run=run-2
```

This rebuilds every dossier from the raw records, re-audits them and serves the app. `run-2` carries the five PayPal
payments. `run-1` is a separate run with a different contract and correctly shows no payments.

**B. Run a fresh seven-party deal with live AI decisions.** Windows PowerShell plus your own NVIDIA NIM key in a local file.

```powershell
.\scripts\run_live_e2e.ps1 -NimKeyFile C:\path\to\nvapi.txt
```

The script:
1. clones the external LEGION components at pinned commits;
2. runs the seven-party episode;
3. runs the independent Judge and the 25 adversarial negatives;
4. builds, audits and serves the result.

**C. PayPal payments.** These are not part of A or B. Each payment needs the platform operator's signed authorization for specific
buyers, and each buyer's approval on PayPal's own page. See [REPRODUCE.md](REPRODUCE.md#c-paypal-sandbox-payments).

## 7. Verification

```bash
python -B -m unittest discover -s tests -v                                   # release tests
pip install -r paypal_adapter/requirements.lock
cd paypal_adapter && python -B -m unittest discover -s tests -t . && cd ..   # 46 payment adapter tests (Windows)
python -B scripts/run_payment_negatives.py                                   # payment negative controls
```

GitHub Actions runs these checks on every push (`.github/workflows/release-checks.yml`). Recorded results: [VERIFICATION.md](VERIFICATION.md).

## 8. Licensing

- **This repository is Apache-2.0** ([LICENSE](LICENSE), [NOTICE](NOTICE)).
- The live seven-party run (B) uses LEGION Core, LEGION-Federation and LEGION-Marketplace.
  - They remain under **PolyForm Noncommercial 1.0.0**.
  - They are fetched at pinned commits and are not copied here.
  - Commercial use of those components requires a separate agreement with Veraxis.
- Mode A, the tests and the payment adapter run without them.
- The organizers have not ruled on this dependency structure.

See [PROVENANCE_AND_LICENSE.md](PROVENANCE_AND_LICENSE.md).
