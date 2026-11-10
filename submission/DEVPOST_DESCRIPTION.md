# LEGION Deal Rescue

*Turn customer requests you cannot fulfil into verified deals, and get paid through PayPal only when each buyer approves.*

## Inspiration

Small merchants routinely say no to custom orders. A single request may be too small for a supplier's minimum order, or it
may need an independent check that nobody can arrange. Several such requests could be served together, but pooling
strangers' money and terms needs trust:

- who agreed to what;
- whose budget limit applies;
- who verified the work;
- that nobody is charged without consent.

## What it does

LEGION Deal Rescue is a merchant workspace that turns individually impossible requests into one verifiable collective deal.

1. **Lost orders.** Five customers each want 20 identical sensor modules for at most $100. The factory's minimum order is 100 units, so each request on its own is refused.
2. **Opportunity.** A marketplace sees only what each of seven independent parties chooses to publish: five buyers, a manufacturer and a qualification engineer. It finds that the five requests together reach the 100-unit minimum.
3. **Deal & approval.** Each party runs its own process with its own key, private policy and AI agent (NVIDIA NIM). Every price change creates a new contract version that needs fresh signatures.
   - $480 is invalidated by an injected test price shock.
   - $540 ($108 per buyer) is refused by all five buyers, because it is over each buyer's own cap.
   - A cheaper design fails the engineer's qualification.
   - **$495 ($99 per buyer)** is signed by all seven.
4. **Work & verification.** Manufacture, certification and shipping are simulated in each party's world, with signed receipts. An independent, read-only Judge reads every party's live state and checks 63 conditions.
5. **Payment & outcome.** Each buyer pays its own $99 through **PayPal Orders v2**.
   - The buyer approves on PayPal's own page.
   - The server confirms `APPROVED` with PayPal before a single capture.
   - A separate process re-reads PayPal's records before the app marks the payment as confirmed.

Every number in the app opens its source record. The Deal Dossier and Execution Passport download as JSON.

## How we built it

- **Parties.** Seven owner processes (LEGION-Federation). Each holds an Ed25519 identity, a disclosure policy, a simulated world and an NVIDIA NIM model agent.
- **Discovery and judging.** Intent discovery and the independent Judge come from LEGION-Marketplace.
- **Merchant app** (this repository, Python standard library):
  - a dossier builder that links every figure to evidence;
  - a read-only server;
  - a single-file UI;
  - an evidence auditor that rejects unsupported claims.
- **PayPal adapter:**
  - a Windows-hosted Orders v2 gateway with a SQLite ledger;
  - durable reservations and idempotent request IDs;
  - no blind retry;
  - an admission decision journaled before every POST;
  - a readback from a separate process.

## PayPal + AI

- **AI.** `nvidia/nemotron-3.5-lightning-30b-a3b` makes every party's accept/reject decision and the coordinator's design choices: 27 decisions per deal.
- **PayPal.** Orders v2 is the payment rail. There is one order per buyer, never a pooled charge.
- **Result.** All five buyers paid in PayPal Sandbox, **$495.00**:
  - five orders and five captures, each approved by that buyer's own Sandbox account;
  - each bound to the buyer's own signed consent and to the seven-party contract;
  - each confirmed by an independent readback;
  - 10 POSTs, 0 retries, 0 duplicate captures.

## Challenges

- **Privacy between parties.** One earlier attempt leaked a party's private value, and the Judge failed it.
- **Delivery vs. payment.** Simulated delivery and payment must never be confused; the app shows them as separate states.
- **A real-world PayPal detail.** PayPal returns the order amount with an extra, empty `breakdown` field, which made our first readback reject a correct payment. We fixed the comparison and kept the failure as evidence.
- **Honest economics.** At these prices the deal has $0 contribution before fees. **This scenario is not profitable.**

## Accomplishments

- Four fresh first attempts with seven independent parties, each passing the Judge (63/63).
- 25 of 25 adversarial negatives, with 0 forbidden effects.
- Five independently verified Sandbox payments.
- Every figure in the UI traced to evidence.

## What we learned

A centralized matcher with the same public data finds the same group. The value is not in matching. It is in:

- per-party consent;
- versioned contracts that cannot silently change a buyer's needs;
- admission checks;
- independent verification before and after money moves.

## What's next

- Rescue custom requests that are actually profitable: buyers whose willingness to pay exceeds vendor cost plus fees.
- Price a real incumbent alternative.
- Obtain an independent acceptance of the payment adapter for production use.

## Verified vs. not claimed

| Verified | Not claimed |
|---|---|
| Seven-party AI negotiation and contract versions | Real customers or suppliers (the scenario is synthetic) |
| Independent Judge, tamper tests, 25 negatives | Physical manufacture or delivery (simulated) |
| 5/5 PayPal Sandbox payments with independent readback | Real money or revenue (Sandbox) |
| Evidence hashes for every figure | Profit ($495 in, $495 cost) |

## Licensing

- This repository is Apache-2.0.
- The live seven-party run uses LEGION Core, LEGION-Federation and LEGION-Marketplace as external pinned dependencies under PolyForm Noncommercial 1.0.0.
- Replay mode, the UI, the tests and the PayPal adapter run without them.

Repository: https://github.com/veraxis-protocol/LEGION-Deal-Rescue
