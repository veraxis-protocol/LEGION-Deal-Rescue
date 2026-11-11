# WO-CAD-003 verification

Run 43038336265 executed Linux-only integration tests on both runners before provisioning the release. Both jobs reported two FileNotFoundError errors. The endpoint test lacked assembly_two_parts.stp and integration class setup lacked assembly_properties.stp. The failed command was python -B -m unittest discover -s tests -v. This was a CI environment and platform selection defect.

Ubuntu installs the immutable pmix archive through scripts/install_pmix.py, installs the SHA-256-pinned Ubuntu bubblewrap package and checks the runner-provided util-linux/prlimit, and proves real sandbox extraction before running all 129 tests. Windows explicitly runs the three supported LEGION modules and all 46 PayPal adapter tests. Release and security controls remain in the workflow. Historical logs in the repository redact machine paths and storage names to satisfy the existing secret and private-path check. The final release package includes the raw failed and successful CI logs.

Independent reproduction from a fresh checkout passed 22/22 original checks, 7/7 prototype checks, 26/26 isolated STEP extracts, 129/129 Linux LEGION tests, 100/100 Windows LEGION tests, 46/46 Windows PayPal tests and build/audit. N07/N09/N10/N14 all passed. The separate source audit verified 860 critical records and their STEP references against original file bytes.

The real browser ran DRAWING â†’ PARTS â†’ LEGION AT WORK â†’ REVIEW â†’ PAYPAL at 1440px and 390px. The uploaded assembly yielded SYN-BRACKET Ã—1 and SYN-PIN Ã—2 with material evidence. Confirmation gated intake. Both flows recorded zero unsupported engineering approvals, zero supplier requests and zero payment effects. Screenshots and API traces are in wo-cad-003/browser.

The exact-head GitHub Actions check is the final release gate. The release package includes the recorded job conclusions and exact SHA. Production engineering qualification remains Z until the independent engineer-adjudicated CAD validation defined in docs/PMIX_INSTALL.md passes.

Two intermediate workflow revisions waited in package provisioning on hosted Ubuntu. The final setup uses the verified Ubuntu package locally and preserves the ordinary-user sandbox smoke test.
