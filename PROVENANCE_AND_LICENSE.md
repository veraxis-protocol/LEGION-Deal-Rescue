# Provenance and license

| Component | Origin | License |
|---|---|---|
| `deal_rescue/`, `scripts/`, `tests/` | Written for this application | Apache-2.0 |
| `paypal_adapter/commerce_adapter/` | Byte-identical to the payment adapter that made the five captures: LEGION-Commerce `0bb385f` (same as `61dd814` for this package). Hashes are in `docs/PAYMENT_RUNTIME.json`. | Apache-2.0, by the copyright owner's decision of 2026-11-09 |
| `paypal_adapter/tests/`, `paypal_adapter/docs/ADMISSION_INTERFACE.md`, `paypal_adapter/design/SOURCE_PINS.json` | LEGION-Commerce, same commit; `tests/test_release_negatives.py` added here | Apache-2.0 |
| `demo_evidence/` | Recorded outputs of the runs and payments listed in [VERIFICATION.md](VERIFICATION.md) (redacted data) | Apache-2.0 |
| LEGION Core, LEGION-Formal-Core, LEGION-Federation, LEGION-Marketplace | External, pinned by commit, not copied | PolyForm Noncommercial 1.0.0 (unchanged) |
| LEGION-Commerce payment orchestration (`commerce_demo`, `commerce_bridge`, `commerce_authority`) | External, referenced by commit and file hash | No license file in that repository |
| Qualified LEGION runtime used for payment admission | Private, not published; commit and decider hash recorded | Not distributed |

**Formal proofs.** LEGION-Formal-Core proves properties of a single collective's admission and completion model. It does not prove the cross-party federation or any PayPal effect. Federation-level protections are tested at run time, not proved.

**Contest note.** This repository carries an OSI license (Apache-2.0). The live seven-party run also needs the PolyForm-Noncommercial components. The organizers have not ruled on whether that meets the open-source rule.
