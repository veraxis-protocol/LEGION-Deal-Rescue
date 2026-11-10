# Challenges and limits

**Synthetic scenario.**
- The five buyers, the factory, the engineer, their prices and the price shock are a fixed demonstration scenario. The price shock is an injected test event. No real customer or supplier is involved.

**Simulated fulfilment.**
- Manufacture, certification, shipping and buyer-ledger entries are simulated inside each party's process.

**Sandbox payments.**
- The five $99 payments are real PayPal Sandbox transactions, approved by Sandbox buyer accounts. They are test money, not revenue or transaction volume.
- Production payments additionally require an independent review and acceptance of the payment adapter, which has not been signed.

**Not profitable.**
- The buyers pay $495 and the vendor costs are $495, so the contribution is $0 before fees.
- Under PayPal's published US rate (3.49% + $0.49; an assumption, since Sandbox charges no fees) the result would be at most −$19.75, before AI, verification and support costs, which are unknown.
- Breaking even would need $103.10 per buyer, above every buyer's $100 cap. See `demo_evidence/HYPOTHETICAL_BREAK_EVEN.json` (labelled hypothetical).
- The commercial opportunity is rescuing custom requests whose buyers will pay more than cost plus fees. That has not been demonstrated with a real customer.

**No proven incremental volume.**
- Whether these deals would have happened anyway through another channel is unknown.
- A real group-purchasing intermediary has not been priced for comparison.

**Matching parity.**
- A centralized matcher given the same public data finds the same group.
- The value shown here is per-party signed consent, versioned contracts, admission checks and independent verification, not better matching.

**Reliability.**
- Four fresh first attempts passed.
- The first campaign (2026-11-07) failed twice before passing: one AI provider error that failed closed, and one private-data leak that the Judge caught.
- The sample is small.

**Payment admission depends on an unpublished component.**
- The admission decisions used during the payments came from a qualified LEGION runtime that is not published (see [docs/PAYMENT_RUNTIME.md](docs/PAYMENT_RUNTIME.md)).
- Its source commit and the decider binary's hash are recorded, but a judge cannot rebuild it from public sources.

**Licensing.**
- The live seven-party run depends on PolyForm-Noncommercial components.
- The organizers have not ruled on this dependency structure.

**No user study.**
- No unaided user test has been run.
