# Challenges and limits

- **Synthetic scenario.** The five buyers, the factory, the engineer, the prices and the price shock are a frozen test fixture. The price shock is an INJECTED / TEST environment event. No real customer or supplier is involved.
- **No physical world effect.** Manufacture, certification, shipping and buyer-ledger payments are simulated inside each owner's process.
- **No PayPal capture.** 0/5 payers, $0. Native payment is blocked by owner-controlled authority (`PAYPAL_STATUS.md`). A single future $99 capture would be a 1/5 partial proof.
- **Not profitable.**
  - $495 receipts against $495 vendor cost gives $0 contribution before fees.
  - Under PayPal's published US fee (an assumption; Sandbox has no fees) the net is at most −$19.75, before inference, verification and support costs, which are unknown.
  - Break-even would need $103.10 per buyer, above every buyer's $100 cap (`demo_evidence/HYPOTHETICAL_BREAK_EVEN.json`, labelled hypothetical).
- **No proven incremental TPV.**
  - Real incremental PayPal volume is unknown (Z).
  - The best real alternative, an incumbent group-purchasing intermediary (A4), has not been priced.
- **Matching parity.** A centralized matcher with identical public data finds the same coalition.
- **First-attempt reliability.**
  - The WO-004 fresh first attempts are 2/2 PASS.
  - The 2026-11-07 campaign failed twice before passing: one NIM provider error (failed closed) and one disclosure leak caught by the Judge.
  - Small sample size.
- **Licensing.** The live run depends on PolyForm-Noncommercial components. Organizer acceptance is not established.
- **No unaided user study.** The 8 comprehension questions were checked by script against screen text, not with people.
