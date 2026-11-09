# Provenance and license

| Component | Origin | License in this repo |
|---|---|---|
| `deal_rescue/` | Written for WO-PAYPAL-LEGION-004 (LEGION-Commerce branches `claude/wo-paypal-legion-004` 1730d70, `claude/wo-004-final-release` 9e1f3d6) | Apache-2.0 |
| `paypal_adapter/` | LEGION-Commerce `codex/wo-com-a04-paypal-sandbox` @ `ff6dcd193d12eb328d5d863881a8d918b8396040`, verbatim subset (runtime, tests, interface doc, lockfiles) | Apache-2.0 by owner decision 2026-11-09 |
| `demo_evidence/runs/A2-fresh-*` | Output of fresh runs 2026-11-09 22:15Z and ~22:50Z on the pinned PolyForm sources (data, redacted) | Apache-2.0 (data) |
| LEGION Core / Federation / Marketplace | External, pinned, not vendored | PolyForm Noncommercial 1.0.0 (unchanged) |

**The Formal Core** (Lean) proves properties of a single collective's admission core. It does **not** prove the cross-owner federation or any PayPal effect. Federation-edge protections here are runtime-tested, not proved.

**Contest note.** The rules require an open-source license for the submitted repository. This repository is Apache-2.0. The live seven-owner run also needs the PolyForm-NC dependencies. Whether that satisfies the organizers is **not established**; no ruling has been obtained.
