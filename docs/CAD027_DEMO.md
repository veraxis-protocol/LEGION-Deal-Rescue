# CAD-027 demo: one real CAD file to an engineering review

The demo takes one real STEP assembly through OpenCascade XCAF to get the parts, reconciles them with the factory BOM, sends them to the ZTL engineering review, and runs the CAD-025 gate. The UI shows four steps in order: DRAWING, PARTS, ENGINEERING REVIEW and RESULT.

**DEMO_GO = T** means the software route works on the real file and every result stays within its proven scope. It is **not** engineering admission. **ENGINEERING_ADMISSION** stays **Z** until two things exist: a complete set of sourced engineering requirements, and an independent Ed25519-signed attestation (CAD-025).

## Easiest way: Judge Mode

`python -m scripts.judge_demo` fetches every input below from its pinned source, verifies its SHA-256, configures the server and opens the 7-screen walkthrough. See the [README](../README.md#judge-quickstart-one-command). The rest of this page explains what runs underneath.

## Inputs

None of these files are in this repository. Their pins are listed in `scripts/judge_manifest.json`.

| Input | Details |
|---|---|
| Assembly | `reBot_B601_DM_v1.1_20260625.step`, 34,840,241 bytes, SHA-256 `a1e301ee03d46589e26d3fc2272d19ba53c1878f0104274695e5c9a88aa512d2`. Any other file is refused. |
| Factory BOM | `hardware/reBot_B601_DM/readme.md` from reBot-DevArm. |
| Performance data | `hardware/reBot_B601_DM/performance_testing/Performance_Testing.md` from reBot-DevArm. |
| ZTL | Checkouts of `ztl-engineer` (tested at `91d1167`), `ztl-stand` (`ae6744f`) and the `ZTL` judge, side by side. |
| Python | 3.12 or later with `cadquery-ocp` 8.0.1 and `cryptography`. The stand also needs `numpy` and `scipy`. |

## Run

```bash
# manual alternative to Judge Mode:
python -B -m deal_rescue.server --evidence demo_evidence --port 8801 \
  --cad027-step <path>/reBot_B601_DM_v1.1_20260625.step \
  --cad027-readme <path>/readme.md \
  --cad027-perf <path>/Performance_Testing.md \
  --ztl-engineer <path>/ztl-engineer
```

Open http://127.0.0.1:8801/ and click **CAD → BOM → ZTL review**. To jump to step N for a presentation, open `/#cad027=N`. It runs the same server stages.

## What each step does

1. **DRAWING:** computes the SHA-256 of the file and compares it with the pin. A mismatch makes the drawing **F** and the run stops.
2. **PARTS:** reads the file with `STEPCAFControl_Reader`, which returns 33 sub-assemblies, 64 part definitions and 326 instances, in mm. The BOM is then matched against the readme:
   - 40 of 40 fabricated parts and 53 of 53 instances match.
   - The optional harness clip (×2) is listed separately and is not in the STEP.
   - The 27 purchased rows are listed beside the STEP's fasteners; they are not force-matched.
   - Material and process come from the readme. Tolerances appear only where the readme states them: line 129, `±0.02 mm GB/T1840-M`, under *CNC Machined Metal Parts*.
3. **ENGINEERING REVIEW:** each candidate reBot predicate is shown with its source lines and the data it is missing. The stand is called only when every input and the requirement itself come from a source that states them for that part.
   - **MGN9-170 rail length: OPEN, RAIL_TOLERANCE = Z.** The rail is a purchased part. The readme's only tolerance belongs to the CNC section, and no source states a tolerance for the rail.
   - **Joint-2 load torque: OPEN.** The load (< 1.5 kg), radius (< 450 mm) and 12 Nm curve come from `Performance_Testing.md`. The arm's self-weight, its centre of mass, the joint-2 motor's rated torque and the joint axis position are not stated anywhere.
   - **reBot production verdict: OPEN.** The stand is not called on invented values.
   - **Separately labelled integration test (not a reBot check):** the real stand judges ztl-stand's own `examples/divider-1pct-req-1pct.json` through `ztl-engineer/mcp_server.py` (`check_design` → `python -m ustand.stand`), and the result is EARNED. This only shows that the ZTL route works. It says nothing about the arm.
   - **CAD-025:** refuses the spec (`PART_FIELD_MISSING_MATERIAL_GRADE`), so ENGINEERING_ADMISSION = **Z**.
4. **RESULT:** a summary of the run, plus a JSON report at `/api/industrial/cad027/report.json`.

STEP coordinates are a nominal model rounded to 0.001 mm. That is the precision of the file's representation, not of manufacturing, and no tolerance is derived from it.

## Fixes recorded

- **OCP 8:** `Bnd_Box.Get()` returns an unbound `Bnd_Box::Limits`, so the box is read through `CornerMin()` and `CornerMax()`. `TDF_LabelSequence` is now `OCP.OCP.collections.Sequence_TDF_Label`.
- **Windows:** the stand's output is decoded as UTF-8. With the default cp1252 code page, `subprocess` silently left `stdout` as None.

## Tests

| Suite | When it runs | Contents |
|---|---|---|
| `tests/test_cad027_demo.py` | Offline; always runs, including in plain `discover` | BOM matching; quantity change gives F; material or tolerance change is detected; unconfirmed tolerance gives Z; STEP rounding is not treated as manufacturing precision; no production EARNED without the stand; changed requirement is detected; rerun is identical; no invented values; incomplete spec or unsigned ZTL blocks admission; substituted SHA gives F; DEMO_GO is not admission. |
| `tests/judge_real_cad027.py` | **Required, never skips** | The real STEP (33/64/326; 40/40 and 53/53; rerun geometry; full run with identical scoped verdicts twice) and the real ZTL stand (labelled integration EARNED; REFUTED and tightened-tolerance cases with a tolerance marked as a test; an unavailable stand is OPEN, never PASS). If an input is missing, the module fails at import. It runs from `python -m scripts.judge_demo` and the CI job `judge-e2e`. |
| `tests/test_judge.py` | Offline | Pinned-source verification (a wrong download is refused; a tampered cache is fetched again); payments bind only to their own contract; a skipped test makes JUDGE_GO F; stale evidence is detected; the CAD endpoints answer 409 with a reason and an action, never 503. |

## Boundaries

No supplier request is sent, no PayPal call is made and the CAD file is not transmitted.
