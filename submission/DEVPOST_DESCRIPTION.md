# LEGION Deal Rescue

*Turn customer requests you cannot fulfill into verified business opportunities — and get paid with PayPal only when each buyer authorizes it.*

## Inspiration

Small merchants routinely say "no" to custom orders. A single request is too small for a supplier's minimum order, or it needs an independent check nobody can arrange.

Several such requests could be served together. But pooling strangers' money and terms needs trust:
- who agreed to what;
- whose budget limit applies;
- who verified the work;
- whether anyone was charged without consent.

## What it does

LEGION Deal Rescue is a merchant workspace that turns individually impossible requests into one verifiable collective deal.

1. **Lost orders.** Five customers each want 20 identical sensor modules for at most $100. The factory's minimum order is 100 units, so each request is refused alone.
2. **Opportunity.** A marketplace sees only what each of seven independent owners chooses to publish (5 buyers, 1 manufacturer, 1 qualification engineer). It finds that the five requests add up to the 100-unit minimum. A match is not permission.
3. **Deal & approval.** Each owner runs its own process with its own key, private policy and an AI agent (NVIDIA NIM). They negotiate one contract, and every price change creates a new version that needs fresh signatures:
   - **v1 $480:** invalidated by an injected test price shock.
   - **v2 $540 = $108 per buyer:** refused by all five buyers, each over its own $100 cap.
   - **Cheaper design ($380):** fails the independent engineer's qualification and is never offered.
   - **v3 $495 = $99 per buyer:** signed by all seven owners.
4. **Work & verification.**
   - Each owner's world executes with signed receipts: manufacture, certification, five shipments and five ledger payments (all simulated).
   - An **independent read-only Judge** reads every owner's live state and returns PASS: 63 of 63 checks, 4 of 4 tamper mutants caught, and 25 of 25 adversarial negatives.
5. **Payment & outcome.**
   - Each buyer pays its own $99 line through **PayPal Orders v2**: create, buyer approval on PayPal, server-side GET confirming APPROVED, capture, and readback from a separate process.
   - Payment proceeds only when owner-signed authority, a one-time permit and that buyer's approval all hold.
   - The app keeps the fulfilment state (SIMULATED) and the payment state separate. It never shows money that PayPal has not confirmed.

Every number in the UI opens its source record: file, record, JSON path and SHA-256. The **Deal Dossier** and **Execution Passport** download as JSON.

## How we built it

- **Owners:** Python owner processes from LEGION-Federation, each holding an Ed25519 identity, a disclosure policy, a world engine and a NIM model agent.
- **Discovery:** LEGION-Marketplace provides intent publication and discovery.
- **Admission:** decisions come from the LEGION Core runtime.
- **Judge:** an independent Judge process that only reads.
- **Merchant app (this repository):**
  - a dossier builder that binds every figure to a retained record;
  - a read-only server;
  - a single-file UI;
  - an evidence auditor;
  - an economic model.
- **PayPal adapter:**
  - Windows-hosted Sandbox Orders v2 gateway;
  - SQLite ledger with durable reservations;
  - idempotent request IDs;
  - no blind retry;
  - global safety stop;
  - separate-process independent readback.

## PayPal + AI

- **AI:** NVIDIA NIM `nemotron-3.5-lightning-30b-a3b` makes every owner's accept/reject decision and the coordinator's design choices. In each fresh run that is 27 model decisions across 7 owners plus the coordinator.
- **PayPal:** Orders v2 is the payment rail, one order per buyer and obligation, never a pooled charge.

**Status: one real PayPal Sandbox payment, independently verified (1 of 5).** Customer A's Sandbox buyer approved $99.00 on PayPal; the order was captured once (COMPLETED) under an owner-signed mission bound to the seven-owner contract, with a fresh Lean admission decision before each POST, and a separate-process readback of PayPal's records confirmed it. The other four payers are not yet authorized; we show them as unpaid. Sandbox test money, not revenue.

## Challenges

- Keeping each owner's private terms private: one earlier attempt leaked a private value, and the Judge failed it.
- Keeping simulated delivery and payment from ever being conflated.
- Being honest about economics. At the frozen prices the deal has $0 contribution before fees. Under PayPal's published fee rate (an assumption) it would be at most −$19.75, so **this scenario is not profitable**. Break-even would need $103.10 per buyer, above every cap.

## Accomplishments

- Two fresh first attempts, each with 7 independent owners and a Judge PASS.
- A $540 price refused by each buyer's own policy.
- An incompatible cheaper design rejected.
- 0 forbidden effects across 25 adversarial negatives.
- 100% of on-screen figures traced to evidence.

## What we learned

- A centralized matcher finds the same coalition. The value is not in matching: it is in per-owner consent, versioned contracts, admission and independent verification before money moves.

## What's next

- Rescue *profitable* custom requests: buyers whose willingness to pay exceeds vendor cost plus fees.
- Complete one authorized Sandbox capture (1/5), then all five.
- Price a real incumbent alternative.

## Verified vs synthetic

| Verified | Synthetic or not done |
|---|---|
| Seven-owner AI negotiation | Customers, prices, price shock |
| Contract versions and denials | Manufacture, shipping, ledger payments |
| Judge PASS, tamper and negative tests | PayPal capture: not executed |
| Evidence hashes | Profit: none |

## Licensing

- This repository: Apache-2.0.
- The live seven-owner run uses LEGION Core, Federation and Marketplace as external pinned dependencies under PolyForm Noncommercial 1.0.0.
- Replay mode, UI, tests and the PayPal adapter run without them.

Repository: https://github.com/veraxis-protocol/LEGION-Deal-Rescue
