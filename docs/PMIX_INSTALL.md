# STEP engineering extraction (WO-CAD-002)

This is an adapter for existing pmix, not a new CAD parser. Extraction and buyer
intent never constitute engineering approval, sourcing authorization or payment
authorization. Independent held-out manufacturing qualification remains **Z**.
No change is made to ZTL, Federation or PayPal authorization rules.

## Pins and installation

* pmix **v0.16.1**, upstream tag object `ab3ad1891b969d34b412b5fdb4b52bdf961102a0`,
  commit `7fdaed5404678bdda689aa879c27b36441b1fc55` (MIT).
* Linux x86-64 official CI artifact `10306453408`, release workflow `34722565424`.
* Binary SHA-256 `cc44b80916fd03c03b74bfa5b011061583c2b96cfc0ca0685ca93cfe1ca0ae43`.
* Experiment ZIP SHA-256 `02afba7871dbad8d2f41c913d952cf5857378b41ee3e50a030b217fce51e5871`.
* Fixture artifact `10306463705`; this is pmix's published test corpus, **not held-out**.
* Python 3.11+; Linux `bubblewrap` and `util-linux` (`prlimit`) are mandatory.
  Use OS-maintained packages. User/network/PID namespaces must work under the
  deployment policy. If blocked, extraction returns Z with diagnostics: do not
  disable isolation or run the purchasing server as privileged root to bypass it.

The repository includes the immutable original release under `vendor/pmix/`.
The installer checks the archive, executable and every manifest member before
Linux test execution. CI uses the same local archive and needs no file-storage
credential or temporary download URL.

```sh
sudo apt-get update
sudo apt-get install -y bubblewrap util-linux
python3 -B scripts/install_pmix.py vendor/pmix/PAYPAL_CAD_001_RELEASE_20261110.zip
PYTHONPATH=tests python3 -B -m unittest -v test_pmix_integration.PmixIntegration.test_successful_extraction_and_bom_reconciliation
cd external/cad-experiment
python3 run_benchmark.py
python3 cad_adapter_prototype.py
cd ../..
python3 -B -m unittest discover -s tests -v
PYTHONPATH=. python3 -B scripts/audit_pmix_provenance.py
python3 -B scripts/build_and_serve.py --evidence demo_evidence --no-serve
```

Run the unchanged PayPal suite on **Windows**, its existing supported DPAPI host;
do not remove `WINDOWS_HOST_REQUIRED` to run it on Linux:

```powershell
cd paypal_adapter
python -m pip install -r requirements.lock
python -B -m unittest discover -s tests -t . -v
```

The accepted run used Windows Python 3.14 and the unchanged lock:
`cryptography==46.0.3`, `cffi==2.1.1`, `pycparser==3.12`.
For browser tests use Playwright **1.62.1** and its supported Chromium, or set
`CHROME_EXECUTABLE` to an existing Chrome. `PYTHON` selects the test server's Python.

```sh
npm ci --prefix scripts/pmix-browser --ignore-scripts
# If no existing Chrome is selected, install this Playwright version's Chromium:
scripts/pmix-browser/node_modules/.bin/playwright install chromium
node scripts/test_pmix_browser.cjs
```

Windows browser tests may target the Linux server through localhost forwarding:
start `python3 -B -m deal_rescue.server --evidence demo_evidence --port 18896` in
the Linux checkout with the verified binary installed, then set
`LEGION_CAD_BASE_URL=http://127.0.0.1:18896` before the browser test. Without this
variable the test driver starts and cleans up its own server.

For an external verified install set `LEGION_PMIX_BINARY` and
`LEGION_CAD_EXPERIMENT`. The binary digest is checked on every extraction.

## API and bounds

`POST /api/industrial/engineering-extract` accepts existing JSON transport
`{"filename":"assembly.step","file_b64":"..."}`. It only extracts; it ignores
commerce claims, creates no intent/payment session and sends no supplier request.
Existing intake and demo-confirm APIs remain available with their existing gates.

STEP limit 16 MiB; legacy formats retain 2 MiB. JSON envelope is at most 23 MB,
socket read deadline 10 s. At most two parser jobs run simultaneously; each pmix
command has 20 s wall time, 10 s CPU, 1 GiB address space, 32 MiB output file,
64 open descriptors, zero core dumps. There are two commands per extraction.
Timeout kills the process group. Scratch input/output is deleted after extraction.
Network/PID/IPC/UTS/user namespaces are isolated; only runtime directories and
the pinned executable are read-only mounted, with private scratch writable.
Host project data, credentials and user home are not mounted into the parser.

All quantities derive from pmix's assembly relations. Missing references, cycles,
depth >64, >300 parts or >100,000 leaf occurrences fail closed. Repeated leaf
instances reconcile into quantities; distinct part IDs/revisions are not merged.
Properties bind only by pmix-provided part/occurrence labels. Conflicting or
ambiguous material/process values remain Z. PMI is retained in document scope;
no automatic assertion of its association to a purchasable part is made.
Raw pmix JSON, unknown features, diagnostics, normalized/declared units, original
STEP entity references and input SHA-256 are exposed for review. Missing field
values remain null/Z, including unspecified process and revision.

The five-screen flow is DRAWING â†’ PARTS â†’ LEGION AT WORK â†’ REVIEW â†’ PAYPAL.
PARTS requires explicit selection and intent confirmation before the read-only
planner. STEP results always hold for independent engineering proof. Exact
part/revision/material/process/file/engineering-digest comparisons are screening
only; no extracted field can authorize a coalition, quote, commitment or payment.

## Qualification boundary and next evidence

The required 26 reference parses and 22+7 checks establish only this corpus and
mechanism. Production qualification stays Z until an independently curated,
held-out dataset supplies engineer-adjudicated part/PMI associations, materials,
processes, units, revisions and expected quantities. Run the same adapter against
those immutable inputs, score every critical field and false approval, and retain
source digests/annotations. PASS requires the agreed field accuracy threshold,
complete provenance and zero unsupported approvals/effects; mismatches FAIL,
missing ground truth PARTIAL. Without that dataset keep Z and hold procurement.


## Hosted verification

Both `release-checks` matrix jobs must pass on the exact PR head. Ubuntu runs
all 129 tests, the original benchmark and prototype, the independent reference
provenance audit and the real browser flow at both supported widths. Windows
runs the three supported LEGION modules (100 tests), all 46 PayPal adapter
tests and N07/N09/N10/N14. Both jobs retain the dossier audit, evidence
immutability check, payment runtime pin check and secret scan. Ubuntu also
runs the existing server smoke test.

The browser driver records actual API responses and verifies the exact five
screen transitions, buyer confirmation and Z payment and engineering gates.
Find the screenshots, API traces and test logs in the Linux Actions artifact.
The verified release package carries the final exact-head CI attestation.
