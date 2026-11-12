# CAD-027 demo: one real CAD file to an engineering review

The demo takes one real STEP assembly through OpenCascade XCAF to get the parts, reconciles them with the factory BOM, checks one requirement with the real ZTL Engineer, and shows the results in the Deal Rescue UI as four steps: DRAWING, PARTS, ENGINEERING REVIEW and RESULT.

## Inputs

None of these files are in this repository.

| Input | Details |
|---|---|
| Assembly | `reBot_B601_DM_v1.1_20260625.step`, 34,840,241 bytes, SHA-256 `a1e301ee03d46589e26d3fc2272d19ba53c1878f0104274695e5c9a88aa512d2`. Any other file is refused. |
| Factory BOM | `hardware/reBot_B601_DM/readme.md` from the same reBot-DevArm source. |
| ZTL Engineer | A checkout of `inventor1975/ztl-engineer` (tested at `91d1167`) with `ztl-stand` beside it (tested at `ae6744f`). The engineer's `ztl_engineer.runner` locates the stand. |
| Python | 3.14 with `cadquery-ocp` 8.0.1 (OpenCascade bindings) and `cryptography`, which the CAD-025 gate needs. |

## Run

```bash
python -m venv --system-site-packages venv
venv/Scripts/python -m pip install -r paypal_adapter/requirements.lock
venv/Scripts/python -B -m deal_rescue.server --evidence demo_evidence --port 8801 \
  --cad027-step <path>/reBot_B601_DM_v1.1_20260625.step \
  --cad027-readme <path>/readme.md \
  --ztl-engineer <path>/ztl-engineer
```

Open http://127.0.0.1:8801/ and click **CAD → BOM → ZTL review**. To jump straight to step N for a presentation, open `/#cad027=N`. It runs the same server stages.

## What each step does

1. **DRAWING:** computes the SHA-256 of the file and compares it with the pin. A mismatch stops the run.
2. **PARTS:** `deal_rescue/industrial/cad_xcaf.py` reads the file with `STEPCAFControl_Reader`. It returns 33 sub-assemblies, 64 part definitions and 326 instances, with dimensions in mm. `cad027_review.reconcile` then matches the BOM against the readme:
   - 40 of 40 fabricated parts and 53 of 53 instances match.
   - The optional harness clip (×2) is listed separately and is not in the STEP.
   - The 27 purchased rows and the STEP's fasteners are listed side by side. They are not force-matched.
   - Material and process come from the readme.
   - Tolerances appear only where the readme states them, which is the CNC parts (±0.02 mm). Printed parts are marked "not stated in source".
3. **ENGINEERING REVIEW:** builds a brick (the input file format of the ZTL stand) from sourced values only:
   - `L_cad`: the length of the MGN9 rail model, from the STEP's bounding box.
   - `L_spec`: the readme's `MGN9-170mm`.
   - The requirement: the readme's ±0.02 mm tolerance.

   The brick goes to `ztl-engineer/mcp_server.py` as the MCP tool `check_design`, which runs `python -m ustand.stand`. The result is EARNED with a guaranteed range for `dL` of ±0.0005 mm. **This covers one predicate only. It does not approve any part or the assembly.** The CAD-025 gate (`ztl_gate.py`) then refuses the spec (`PART_FIELD_MISSING_MATERIAL_GRADE`), so engineering admission stays **Z**.
4. **RESULT:** a summary of the run, plus a JSON report at `/api/industrial/cad027/report.json`.

## Fix for the OCP failure

The earlier failure (`F_OCCT_EXCEPTION`) had a specific cause. With `cadquery-ocp` 8.x, `Bnd_Box.Get()` returns the C++ struct `Bnd_Box::Limits`, which has no Python binding, so the call fails with "Unregistered type". The STEP import itself had succeeded. `cad_xcaf.bbox()` reads the box through `CornerMin()` and `CornerMax()` instead.

OCP 8 also moved the class `TDF_LabelSequence`. It is now `OCP.OCP.collections.Sequence_TDF_Label`.

## Tests

```bash
CAD027_STEP=... CAD027_README=... ZTL_ENGINEER_DIR=... python -B -m unittest tests.test_cad027_demo -v
```

The file has 14 tests:
- **Offline** (always run): BOM matching, quantity change, material or tolerance change, no invented values, SHA substitution, missing requirements giving Z, an unsigned result failing CAD-025, and sourced brick values.
- **Real stand** (when the inputs are present): EARNED; REFUTED when the length is out of tolerance; a different verdict when the tolerance is tightened.
- **Real STEP** (when the inputs are present): XCAF structure, 40/40 and 53/53, and a rerun reproducing the result.

Without the real inputs, those tests are skipped, never faked.

## Boundaries

- No supplier request is sent, no PayPal call is made and the CAD file is not transmitted.
- Engineering admission is **T** only when CAD-025 receives an Ed25519-signed attestation from an independent verifier covering every part and requirement. No such attestation exists here, so it is **Z**.
