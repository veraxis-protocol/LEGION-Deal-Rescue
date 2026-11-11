# WO-CAD-002 acceptance

GO for the read-only pmix 0.16.1 integration on the tested hosts and reference corpus. Production engineering qualification remains Z. Baseline commit 805a30b1a38772b0683cb91941da633706571b34.

| Check | Result |
|---|---|
| Original experiment and prototype | 22/22 and 7/7 |
| Original reference STEP extract and product | 26/26 each |
| Installed adapter inside unprivileged Linux bubblewrap | 26/26 |
| Existing LEGION and new integration tests | 100/100 and 29/29 |
| Build and audit | PASS |
| PayPal on Windows Python 3.14 with existing lock | 46/46 |
| Browser Drawing to Parts and confirmation at 1440px and 390px | PASS at both |

The verified installer checked the original ZIP, binary digest and manifest members. The full Linux suite ran against that installed binary and fixture directory. The real adapter retained file SHA-256 and source entity references for 860 critical fields and PMI records. Extracted records include 287 dimensions, 380 GD&T tolerances and 127 datums. The original parser reported 17 unsupported entities and 20 diagnostics. Assembly evidence included SYN-BRACKET ×1 with SYN-ALLOY-17 and SYN-PIN ×2 with SYN-STEEL-4.

The tested flows produced zero unsupported engineering approvals, supplier requests or payment effects. STEP intent confirmation is bound to the drawing and selected quantities. Engineering and execution gates stayed Z after confirmation. Negative tests cover incompatible specifications, missing values, parser failures and authorization boundaries. Existing ZTL, Federation and PayPal authorization code retains its baseline behavior.

Linux executed the PayPal suite with five existing WINDOWS_HOST_REQUIRED errors. Windows is the supported DPAPI host and passed all 46 tests with the exact lock. The earlier Windows-only pmix attempts and storage failure are retained as historical evidence. The recovered run corrected the revision test setup to replace both original revision labels in its controlled variants. Assertions continued to require the exact revised values.

The Linux server ran as an ordinary WSL user with bubblewrap 0.9.0 and util-linux 2.39.3. Browser tests used Playwright 1.62.1 and Windows Chrome 156.0.8078.76 against that local backend. Installation and replay instructions are in docs/PMIX_INSTALL.md.

L1 verified the reference extraction, quantity reconciliation, provenance and fail-closed purchasing gates. L2 supports drawing review and selection. GAIA2 Pass@1 and cost were outside this experiment. L3 verified the separation of extraction, buyer intent and authority in the exercised paths.

General industrial accuracy and part-to-PMI association require an independent held-out CAD corpus with engineer-adjudicated ground truth. Freeze its hashes and score the same pinned adapter against agreed accuracy thresholds, critical provenance and zero unsupported approvals. PASS requires all three. Wrong results FAIL and missing ground truth yields PARTIAL. The present run independently verified the 26 reference cases. Keep production qualification Z until the held-out test passes.
