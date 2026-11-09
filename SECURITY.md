# Security and privacy

**No secrets in this repository.**
- The NIM key is read from a local file path you pass at run time.
- PayPal client credentials stay DPAPI-sealed on the operator's Windows host and are never exported.

**Least authority.**
- The Deal Rescue server is read-only: it binds `127.0.0.1` and has no write endpoints, no model calls and no PayPal calls.
- The PayPal adapter has no `--force`, no mock live mode and no test-key fallback.
- Every POST needs current signed authority, a held reservation and provider-confirmed buyer approval.

**Owner isolation.**
- Each of the seven owners runs in its own process with its own key and private terms.
- The Judge checks that no owner-private value appears outside its owner. The 2026-11-07 attempt 2 failed exactly this check and is kept as negative evidence.

**Public evidence is redacted.**
- `demo_evidence` excludes owner configs and private journals, local endpoints, and historic PayPal order and merchant identifiers.
- The leakage scan used to publish it is part of the release record.

**Reporting.** Open a private security advisory on this repository.
