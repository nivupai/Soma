# M33 skull protocol v3.1: v3 plus an MRI-only head crop (draft until sealed)

Status: **DRAFT** until the owner runs `python -m scripts.seal_m33_skull_v31 --approved-by <name>`,
which records this file's SHA256 **and the inner-skull model's SHA256** in
`configs/m33-skull-v31-freeze.json`. `scripts/run_m33_skull_v31.py` refuses to score without that
seal or with a different model file. v3.1 supersedes v3 (`docs/MILESTONE33_SKULL_PROTOCOL_V3.md`),
which was sealed but never scored on any test case.

## Why the amendment

On the SynthRAD2025 head-and-neck test scans, FreeSurfer's `mri_normalize` took about 400 minutes
per scan (about 1 minute on brain-only scans), because the field of view includes the neck and
shoulders. SynthSeg also ran out of memory on them. No skull model was built and nothing was
scored on any test case under v3.

## The only change from v3

Before any other step, each T1 is cropped by `soma.anatomy.fs_skull.crop_head_top`, a rule
that uses only the MRI:
- find the most superior slice whose Otsu foreground has at least 1% of the largest slice's
  foreground, and keep everything above it;
- drop slices more than **220 mm** below that top;
- cut the in-plane extent to the remaining foreground bounding box plus **10 mm**;
- keep world coordinates exactly (the affine is shifted).

FreeSurfer, SynthSeg and the refinement features all use the cropped T1. CT and its mask are
not cropped, and the CT truth, region, flags, metrics and decision rule are exactly as in v3.

The inner-skull model is retrained in exactly the v3 way, on the 60 development cases processed
with the crop: `reports/milestone33/skull-dev-crop/refine-model-v3.1-final.pkl`, SHA256
`36c6391132d699decc9d8e34c176c612aac48ef49fddff574b9096206de67f65`. The seal verifies this hash.

## Check on the 60 development cases (leave-one-centre-out, mean |d| / HD95, mm)

| Cases | Version | Inner skull | Outer skull | Scalp | Thickness error |
|---|---|---|---|---|---|
| All 60 | v3, no crop | 1.56 / 6.15 | 1.90 / 4.89 | 1.22 / 4.28 | +0.49 |
| All 60 | **v3.1, crop** | 1.46 / 5.58 | 1.91 / 4.91 | 1.23 / 4.28 | +0.44 |
| 56 QC-clean | v3, no crop | 1.07 / 4.25 | 1.75 / 4.24 | 1.17 / 4.18 | +0.46 |
| 56 QC-clean | **v3.1, crop** | 1.07 / 4.23 | 1.78 / 4.30 | 1.21 / 4.21 | +0.50 |

The crop leaves development results unchanged within a few hundredths of a millimetre. These
scans are already brain-sized, so the crop mostly removes air.

## Test data, method, metrics and decision rule

As in v3: SynthRAD2025 Task 1 head-and-neck, all 156 cases, each scored once. Every v3 rule applies
unchanged, including the VALIDATED / QC_ONLY / NOT_READY decision with the owner-approved limits.

CT-only exclusion flags for all 156 test cases were computed before this amendment, to set the
processing order. They do not involve any skull model or score.
