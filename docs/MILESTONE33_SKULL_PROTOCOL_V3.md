# M33 skull protocol v3: learned inner skull, external test on SynthRAD2025 head-and-neck

Status: **DRAFT** until the owner runs `python -m scripts.seal_m33_skull_v3 --approved-by <name>`,
which records this file's SHA256 in `configs/m33-skull-v3-freeze.json`. The runner
`scripts/run_m33_skull_v3.py` refuses to score without that seal, or if the inner-skull model
file's SHA256 differs from the one fixed below.

## Why v3

v2 (sealed, scored once on the 120 SynthRAD2023 held-out cases) was `NOT_READY` only because
the inner skull missed its bar (2.41 mm, HD95 5.48 mm). v3 adds a learned inner-skull
refinement. Because the v2 held-out cases have been used, v3 is tested on a **new external
dataset**.

## What was seen before sealing (disclosed)

- All v3 development used only the 60 SynthRAD2023 development cases.
- From the test dataset, two cases were inspected for headers, voxel size, field of view and
  MR contrast (fat bright, so T1-weighted). No skull model was built and nothing was scored on
  any test case.

## Method (fixed)

1. v2 pipeline unchanged: FreeSurfer 8.1.0 watershed BEM on conformed, N3-corrected, normalised
   T1; normal offsets inner −3.28, outer −3.63, scalp −0.95 mm; MRI-only QC ratio in [0.80, 1.80].
2. **Learned inner-skull refinement** (`soma.anatomy.inner_skull_refine`). Each inner-skull vertex
   gets MRI-only features: the T1 profile along the outward normal (−10 to +10 mm), its gradient,
   the signed distance to SynthSeg's intracranial boundary along the same profile, and direction.
   A gradient-boosted regressor predicts the signed distance to the CT inner skull. The vertex is
   moved by minus the prediction, smoothed over the mesh (10 iterations) and clipped at ±6 mm.
   - Model: `HistGradientBoostingRegressor(loss="absolute_error", max_iter=300,
     learning_rate=0.08, max_leaf_nodes=31, random_state=11042)`, scikit-learn 1.9.1, trained on
     region vertices of all 60 development cases (targets clipped to ±12 mm).
   - Model file SHA256: `9afbbce8bcd3ec15a02aa06a656cd0c895ea95ab79b673fed88f4f2ab0943b5b`
     (reproducible with `scripts/dev_m33_inner_skull.py`).
3. SynthSeg 2.0 robust on each test MR (as before).

## Test data

SynthRAD2025 Task 1, head-and-neck region (Zenodo record 15373853, CC BY-NC 4.0, centres A–C
only; centre D's restricted licence does not apply). Every case with MR, CT and mask is
requested (156 cases). MR and CT are 1 × 1 × 3 mm; FreeSurfer conforms the MR to 1 mm.
Scans that cut through the cranial vault are expected. They are caught by the v2 truncation
and crop flags and leave the primary analysis, and the all-cases analysis still reports them.

## CT truth, region, flags, metrics and decision rule

Unchanged from v2 (`docs/MILESTONE33_SKULL_PROTOCOL_V2.md`): CT truth with the three-axis cavity
fill; bone at 300 HU primary and 200/400 HU sensitivity; `FLAGS_V2` plus the MRI-only QC; area-weighted
signed / absolute / HD95 distances and thickness error; subject bootstrap (seed 11042).

- **VALIDATED**: ≥ 15 evaluable cases; inner skull and scalp mean |d| ≤ 2 mm and HD95 ≤ 5 mm
  (bootstrap upper bounds below); outer skull ≤ 3 mm and ≤ 7 mm; thickness-error CI within ±2 mm.
- **QC_ONLY**: inner skull and scalp pass, outer skull or thickness do not.
- **NOT_READY**: otherwise.

The label applies to this method on T1-weighted MRI comparable to the test data. It is reported
per boundary and per centre, with the all-cases and 200/400 HU sensitivity analyses.

## Development evidence (60 cases, leave-one-centre-out, not a claim)

On QC-clean cases, inner-skull mean |d| dropped from 2.69 to 1.07 mm and HD95 from 7.20 to
4.25 mm. Per centre: A 1.86, B 1.05, C 1.77 mm (all cases). Outer skull 1.9 mm and scalp
1.2 mm were unchanged. The external test differs from development in scanner, slice thickness
(3 mm), clinical indication and field of view, so a worse result there is possible and would be
reported as is.
