# Industrial sourcing and coalition discovery

This page documents a **read-only research and candidate-formation component** integrated into the existing Deal Rescue merchant app. It does not create orders, charge PayPal, contact potential buyers, or admit a contract to LEGION Federation.

Open Deal Rescue normally. Click **Industrial Sourcing** in the header. Three fixture scenarios are available:

- **Coalition**: five separate synthetic, explicitly opted-in procurement enquiries for the same illustrative SLS/PA12 bracket, revision C, 20 units each. With fixture-only all-in pricing, the coalition is $2,300 versus direct $3,850, split $3,400 and single additive manufacturing $4,100. This is **not a live supplier quotation**.
- **Direct**: change only the fixture direct route to $2,000; system must choose direct procurement instead of inventing a rescue.
- **Mismatch**: buyer five has a different revision; it cannot be pooled with the other four. A 100-unit MOQ quotation fails for the remaining 80 units.

The supplier registry combines 36 researched marketplace/factory/directory entrypoints, an indexed 48-member HP Additive Manufacturing Network snapshot (3 names overlap), and 3 new primary company sources. **87 records; 84 net of observed aliases.** This is neither all 3D printing manufacturers worldwide nor evidence any record will accept a specific order. Indexed HP directory members are not individually authenticated by LEGION. The HP page renders its directory dynamically, so the indexed snapshot is not a complete independently fetched census.

**Evidence boundaries**

- Buyer prospects: opt-in evidence required for actual outreach, not assumed from a public marketplace listing. Synthetic fixtures are never real buyer consent.
- Technical scope: identical spec digest, revision, process and material are necessary for grouping, but not sufficient to prove manufacture or mechanical performance. CAD/DFM is separate.
- ZTL Engineering: `verify_ztl_binding()` is the pinned independent-verifier contract. Without an authenticated ZTL Engineering endpoint and an externally verified proof receipt for a supported engineering model, verdict is **Z**. An unsupported arbitrary STEP/STL geometry cannot be declared Lean-proved.
- Supplier discovery: companies listed in directories are not approved suppliers. Pricing, process capacity, actual stock, authentic firm quotations, delivery and warranty remain **Z** until independently verified.
- Federation: existing runtime remains unchanged. New records are **proposals only**, not authorized commitments.
- PayPal: the separately evidenced five historical Sandbox captures remain in their original contract; this integration records **0 new captures**.

**Read-only API**

`GET /api/industrial/registry` — source-linked discovery entries and uncertainty.

`GET /api/industrial/cases` — test-only cases.

`GET /api/industrial/decision?case=coalition|direct|mismatch` — decision, gate status, sourcing candidates.

`GET /api/industrial/passport?case=...` — download proposal and T/F/Z passport.

`GET /api/industrial/rfq?case=...` — download a non-binding unsent RFQ without buyer identifiers or private CAD.

No corresponding POST handler is added.

**Next integration gate**: independent ZTL Engineering proof receipt for a supported engineering formula; one genuine buyer-authorized demand; supplier-confirmed landed quotation; independently authenticated multi-owner consent; matching Federation admission; only then a new, separately authorized PayPal Sandbox payment and independent provider readback.
