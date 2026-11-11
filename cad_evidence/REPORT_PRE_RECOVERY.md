# WO-CAD-002 — partial implementation / NO-GO

Baseline: `805a30b1a38772b0683cb91941da633706571b34`.
Development branch: `wo-cad-002-pmix-integration`. This is not DONE or accepted.

## Evidence and actual extraction

The original report, benchmark, checks, adapter, source manifest and negatives
were read before edits. All 134 SHA256SUMS entries verified before executing the
bundled pinned binary in WSL. Original commands actually ran: **22/22 + 7/7**, with
**26/26 extract and 26/26 product** results. The replay measured 287 dimensions,
380 GD&T tolerances, 127 datums, 33 product records and five assembly relations.
Seventeen unsupported entities and 20 diagnostics remain visible; no recall or
independent industrial accuracy claim is made. Archive source SHA-256 and binary
pin are recorded in `docs/PMIX_INSTALL.md`.

The new mapping code independently mapped all 26 archived actual JSON outputs,
retaining Z and disabled checkout. This validates JSON mapping only, not new
sandbox execution. Source/quantity example: SYN-BRACKET=1, SYN-PIN=2, explicit
materials SYN-ALLOY-17 and SYN-STEEL-4; unspecified revision/process remain Z.

## Changes prepared

* Existing pmix JSON → provenance-bearing STEP BOM/engineering evidence adapter.
* Mandatory bubblewrap namespaces and subprocess resource/time/output limits;
  hash verification on each execution; no unsafe platform/sandbox fallback.
* Existing CSV/JSON/DXF/SVG/PDF behavior retained; STEP gets 16 MiB cap.
* Read-only engineering-extract API, bounded JSON/socket read, no commerce session.
* STEP selection bound to file digest/part/quantity; strict engineering compatibility
  screening; no coalition, quote, supplier order or payment authority from extraction.
* Five-screen browser flow, specifications/evidence and mandatory parts confirmation.
* 29 new test methods, real browser test driver, pinned archive installer and docs.

## Executed validation and blockers

Existing LEGION tests: **100/100 PASS** inside full discovery. Build/audit PASS.
PayPal regression: **46/46 PASS** (Windows Python 3.11.9, cryptography 46.0.3,
cffi 2.0.0, pycparser 2.23; no live calls).

Full discovery is **FAIL**, not a regression acceptance pass: 104 executed,
103 passed, one new HTTP failure and one class-setup error. Twenty-five new
binary integration methods could not execute after setup failed on Windows.
The setup error is mandatory Linux sandbox availability, not a skipped test.
The Linux smoke attempt failed at OS execution before pmix, with I/O error.

Both browser sizes actually ran and **FAIL** because real components were not
extracted on the Windows fallback server. No JS page errors; observed POSTs
before confirmation were extraction only. Screenshots are failure evidence.
Nothing is mocked to obtain PASS.

C: reached 0 bytes during test dependency provisioning; WSL binaries returned
I/O error, then Ubuntu stopped with `Wsl/Service/E_FAIL`. A redundant locally
downloaded ZIP was removed; original evidence storage release remains intact. A previous
temporary-cache deletion was rejected by automatic review and not performed.
No user documents or other projects were cleaned. Storage/WSL recovery is needed.

## Required continuation / six-part evidence path

Gap: new Linux isolation, complete integration suite and successful browser
extraction. Required evidence: sandbox output, all 129 discovered tests passing,
26 isolated reference parses, 46 PayPal passes, build PASS and two browser PASSes.
Obtain it by restoring host storage and Ubuntu, installing pins and following
`docs/PMIX_INSTALL.md`. Independently feasible checks already executed are logged
above; the unsafe sandbox bypass was not used. PASS requires every work-order
condition, FAIL any mismatch/unauthorized effect, PARTIAL missing execution.
Next: recover at least 2–3 GB, rerun the sandbox smoke then all suites unchanged;
repair actual defects if found. If unavailable, keep draft/NO-GO and no integration
release. Independent held-out engineering qualification remains Z and requires
engineer-adjudicated immutable inputs as specified in the installation document.

Work type: CAPABILITY EXPANSION with INVARIANT VERIFICATION. L1 checks extraction,
provenance, quantities, compatibility and no-effect boundaries. L2 enables review
of actual STEP demand; no GAIA2 ≥95% Pass@1 or cost improvement was measured.
L3 preserves separation of parsing, engineering truth, user intent and authority;
full new-chain correctness requires the execution evidence above.
