# Judge access

**No account, key or payment is needed to inspect the product.**

```bash
git clone https://github.com/veraxis-protocol/LEGION-Deal-Rescue.git && cd LEGION-Deal-Rescue
python -B scripts/build_and_serve.py --evidence demo_evidence
```

Then open `http://127.0.0.1:8795/?run=run-2`. This rebuilds and re-audits every figure from the recorded runs and payments.
Screen 5 shows the five PayPal Sandbox payments, each with its consent, authorization, order, capture and readback.

**Tests.**
- `python -B -m unittest discover -s tests -v`
- `cd paypal_adapter && python -B -m unittest discover -s tests -t .`, which needs `cryptography`.

**Fresh AI run (optional).** Windows, with your own free NVIDIA NIM key:

```powershell
.\scripts\run_live_e2e.ps1 -NimKeyFile <file>
```

**PayPal.** The five payments were made in PayPal Sandbox and are shown from their recorded evidence. A new payment
requires the platform operator's signed authorization and a buyer's approval on PayPal, so judges cannot trigger one from the app.
No hosted instance is provided.
