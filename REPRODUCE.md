# Reproduce

There are three modes, and each needs something different:

| Mode | Needs | Produces |
|---|---|---|
| A. Recorded runs | Python 3.11+ | Rebuilt dossiers, audit, the app |
| B. Fresh seven-party run | Windows PowerShell, git, Python 3.11+, internet, your NVIDIA NIM key | A new run judged live by the independent Judge, plus 25 negatives |
| C. PayPal Sandbox payments | Owner authorization, PayPal Sandbox accounts, Windows | Real Sandbox orders and captures |

## A. Recorded runs (no credentials)

```bash
git clone https://github.com/veraxis-protocol/LEGION-Deal-Rescue.git && cd LEGION-Deal-Rescue
python -B scripts/build_and_serve.py --evidence demo_evidence --no-serve   # rebuild + audit
python -B -m unittest discover -s tests -v                                 # release tests
python -B scripts/build_and_serve.py --evidence demo_evidence              # serve http://127.0.0.1:8795/?run=run-2
```

Expected results:
- `audit_all_pass: true`.
- Both runs: Judge `PASS_COMPLETED` with 63/63 checks; every on-screen figure and replay event resolves to a record.
- Negative matrix: 15/15.
- `run-2` shows 5 of 5 buyers paid ($495.00, Sandbox). `run-1` shows no payment, because it is a different contract.

Payment adapter tests and payment negative controls:

```bash
pip install -r paypal_adapter/requirements.lock
cd paypal_adapter && python -B -m unittest discover -s tests -t . && cd ..
python -B scripts/run_payment_negatives.py
```

## B. Fresh seven-party run

```powershell
.\scripts\run_live_e2e.ps1 -NimKeyFile C:\path\to\nvapi.txt
```

The script clones these external components (PolyForm Noncommercial 1.0.0) into `external/`:

| Component | Pinned commit |
|---|---|
| LEGION Core | `d083c44af2526e38068e0220891cd0bb5fce52af` |
| LEGION-Federation | `9d2a32a5c32758bea1ad2200955da1cc9213356c` |
| LEGION-Marketplace | `906ec0f553c0f8076127f7abab98825e188342ef` |

Later commits to Federation and Marketplace change documentation only.

Before running, the script checks the Judge source hash, `9146122791d2d2a6f4cada2019c825b2c4925b6e4182fe91f55a7bae74f2992f`. The model is `nvidia/nemotron-3.5-lightning-30b-a3b`; you can override it with `LMF_NIM_MODEL`.

A fresh run is a new first attempt; its outcome is whatever the Judge returns. Track record so far:
- three fresh first attempts, all passed;
- the first campaign on 2026-11-07 passed 1 of 3 attempts. One NIM provider error failed closed, and one private-data leak was caught by the Judge.

A fresh run has its own contract, so it shows no PayPal payment.

## C. PayPal Sandbox payments

Payments are deliberately not automated. They use the LEGION-Commerce payment orchestration at the commits listed in [docs/PAYMENT_RUNTIME.md](docs/PAYMENT_RUNTIME.md), on a Windows host with:

- PayPal Sandbox REST credentials, stored with Windows DPAPI under `%LOCALAPPDATA%\Veraxis\LEGION-Commerce\` (never in this repo);
- the owner's control key (passphrase-protected);
- one PayPal Sandbox Personal buyer account per buyer.

Steps (Windows PowerShell, inside the LEGION-Commerce checkout):

1. Draft the payment authorization from a Judge-passed run:
   ```powershell
   python -m commerce_demo.lmf007 prepare --merchant <sandbox merchant id> --contract-run <run dir> --payers b1
   ```
2. The owner reviews and signs it:
   ```powershell
   python -m commerce_demo.mission authorize
   ```
3. Execute:
   ```powershell
   python -m commerce_demo.lmf007 run
   ```
   For each payer it prints a PayPal approval link. The buyer approves in a browser on the same machine (the return goes to `127.0.0.1:8765`). The run then captures once and runs the independent readback.

To show the results in the app, copy the run's mission, events, ledger export and readback files (merchant ID redacted) into `demo_evidence/paypal_runs/<run>/`, then rebuild.
