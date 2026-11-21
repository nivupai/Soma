# M33 skull protocol v2: calibrated FreeSurfer watershed vs CT bone (draft until sealed)

Status: **DRAFT** until the owner runs `python -m scripts.seal_m33_skull_v2 --approved-by <name>`,
which records this file's SHA256 in `configs/m33-skull-v2-freeze.json`.
`scripts/run_m33_skull_v2.py` refuses to score without that seal. v2 replaces v1
(`docs/MILESTONE33_SKULL_PROTOCOL.md`), whose results are unreliable because of a CT-truth bug
(see `docs/MILESTONE33_SKULL_RESULTS.md`).

## What was seen before sealing (disclosed)

- All 180 cases were scored under v1 with the T1-only baseline and the buggy CT truth.
- Development used **only** the 60 development cases in `configs/m33-skull-v2-split.json`
  (20 per centre, seeded). Every choice below was made on those cases. **No held-out case has
  been scored with the v2 method or the fixed CT truth.**

## Question

How close is Soma's measured MRI skull model, FreeSurfer's watershed BEM with fixed,
development-calibrated offsets, to independent CT bone on unseen cases, and what readiness
label does it earn?

## Data and split

SynthRAD2023 Task 1 brain (CC BY-NC 4.0, aggregates only). Held-out set: the 120 cases listed
under `held_out` in `configs/m33-skull-v2-split.json` (40 per centre), scored once.

## Method (fixed)

1. `mri_convert --conform` → `mri_nu_correct.mni --n 1` → `mri_normalize` gives `T1.mgz`;
   `mne.bem.make_watershed_bem` (defaults, no atlas) gives inner skull, outer skull and scalp.
   FreeSurfer 8.1.0, arm64.
2. Surfaces are converted to scanner RAS (`soma.anatomy.fs_skull`) and each is moved along its
   outward normal by a **fixed offset: inner skull −3.28 mm, outer skull −3.63 mm, scalp
   −0.95 mm**. These are minus the median signed biases on the 60 development cases.
3. **MRI-only quality check** (no CT): watershed inner-skull volume ÷ SynthSeg intracranial
   volume must lie in [0.80, 1.80]. A failing head is flagged (it would be labelled
   `NOT_READY` on its own) and leaves the primary analysis.

## CT truth (fixed)

As v1, except that the cranial cavity is filled along all three axes and then in 3D (the v1
bug fix, with a regression test). Bone at HU > 300 is primary; the truth is rebuilt at 200 and
400 HU as sensitivity analyses. A failure at one sensitivity threshold is recorded and does not
drop the case. The evaluation region rule is unchanged from v1.

## Exclusion flags (v2, `FLAGS_V2`)

| Flag | Rule |
|---|---|
| Metal | > 10 voxels ≥ 3000 HU in the region (unchanged) |
| Vertex truncation | **bone** (HU > 300) in the 3 most superior slices; scalp tissue there no longer counts |
| Skull defect | cavity ÷ (slice-wise convex hull of bone minus bone) over the upper half of the cavity **< 0.80**; uncovered-patch rule kept; the 900 mL minimum is removed |
| Field-of-view crop | **> 200** CT bone voxels within 2 voxels of the head-mask edge inside the region |
| MR/CT consistency | reported only, never excludes (bright diploic marrow made it meaningless) |
| MRI-only QC | see Method 3 |

On development cases these flagged 27 of 60 (skull defect 16 at the earlier 0.90 cut, metal 9,
truncation 4, crop 4). The defect cut was then set to 0.80, at a natural gap in the development
distribution (the craniectomy case and crop cases fall below it, intact heads lie at 0.85 or above).

## Metrics and decision rule (unchanged from the owner-approved v1)

Signed mean, symmetric mean absolute distance and HD95 per boundary, plus skull thickness error,
subject bootstrap (seed 11042, 2,000 repetitions), primary = 300 HU, unflagged, QC-passing.

- **VALIDATED**: ≥ 15 evaluable cases; inner skull and scalp mean |d| ≤ 2 mm and HD95 ≤ 5 mm
  (bootstrap upper bounds below); outer skull ≤ 3 mm and ≤ 7 mm; thickness-error CI within ±2 mm.
- **QC_ONLY**: inner skull and scalp pass, outer skull or thickness do not.
- **NOT_READY**: otherwise.

The result is also reported per boundary and per centre, with the all-cases and 200/400 HU
sensitivity analyses next to it.

## Development results that motivated this (60 cases, not a claim)

Fitting the offsets on two centres and testing on the third (leave-one-centre-out): mean |d|
inner skull 3.26 mm, outer skull 2.02 mm, scalp 1.29 mm. Without the 3 QC failures and the
craniectomy case: inner skull 2.69 mm (HD95 7.2), outer skull 1.89 mm (HD95 4.4), scalp 1.24 mm
(HD95 4.2). Two alternatives were tried and rejected: a SynthSeg-based inner skull (4.42 mm)
and atlas-guided watershed (3.35 mm). **Expected outcome on that basis: inner skull likely
misses the 2 mm / 5 mm bar, so the label is likely `NOT_READY`, with outer skull and scalp
passing.** The bar is not lowered to change this.
