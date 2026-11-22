# M33 skull v2 results: calibrated FreeSurfer watershed vs CT (120 held-out cases)

Protocol: `docs/MILESTONE33_SKULL_PROTOCOL_V2.md`, sealed by the owner in
`configs/m33-skull-v2-freeze.json` before any held-out case was scored. Each held-out case was
scored once. Aggregates (CC BY-NC 4.0, no case IDs): `experiments/milestone33/skull-v2-aggregate.json`.

## Outcome

**Readiness: `NOT_READY`.** Only the inner skull misses its bar. The outer skull, scalp and
skull thickness all pass.

| Check | Result |
|---|---|
| Evaluable cases (unflagged, MRI-QC pass) | 67 of 120 (≥ 15 required) |
| Inner skull: mean \|d\| ≤ 2 mm, HD95 ≤ 5 mm | **fail**: 2.41 mm (2.23–2.57), HD95 5.48 mm (4.94–6.12) |
| Outer skull: ≤ 3 mm, ≤ 7 mm | pass: 1.58 mm (1.45–1.73), HD95 3.50 mm (3.24–3.79) |
| Scalp: ≤ 2 mm, ≤ 5 mm | pass: 1.13 mm (1.05–1.20), HD95 4.29 mm (3.66–4.98) |
| Thickness error CI within ±2 mm | pass: +0.04 mm (−0.36 to 0.45) |

Subject bootstrap means with 95% intervals, 300 HU, primary analysis. Signed biases are small
(inner +0.58, outer +0.36, scalp +0.09 mm), so the development-calibrated offsets carried over to
unseen cases.

## Robustness

| Analysis | Inner skull | Outer skull | Scalp (mean \|d\|, mm) |
|---|---:|---:|---:|
| Primary (67) | 2.41 | 1.58 | 1.13 |
| All 120, flagged included | 2.90 | 1.72 | 1.12 |
| Bone at 200 HU | 2.49 | 1.57 | 1.13 |
| Bone at 400 HU | 2.60 | 1.64 | 1.13 |
| Centre A / B / C | 1.80 / 2.85 / 2.54 | 1.47 / 1.76 / 1.38 | 0.85 / 1.26 / 1.32 |

Flags (a case can carry several): skull defect 24, metal 20, vertex truncation 20, crop 14,
MRI-only QC 1. No case failed to run.

## What this means

- Soma now has a measured MRI head model whose **scalp and outer skull agree with CT to about
  1.1–1.6 mm** on unseen patients from three centres, with unbiased skull thickness.
- The **inner skull is about 0.4 mm short of its 2 mm target** and is weakest at centres B and C.
  So no head built this way is `VALIDATED` yet. Under the v2 rule the label is `NOT_READY`.
  The bar was not changed after seeing results.
- Compared with the T1-only estimate (v1, about 4–6 mm off), this is a large step forward.
- Next lever: the inner skull. Candidates are a learned skull segmentation (CT-supervised on the
  development split only) or combining SynthSeg's CSF boundary with watershed in a locally
  weighted way. Any of these needs a v3 protocol and fresh held-out data, because this held-out
  set has now been used once.
