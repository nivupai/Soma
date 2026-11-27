# M33 inner skull: training-improvement experiments (development only)

Not a sealed claim. All numbers come from leave-one-centre-out on the 180 SynthRAD2023 brain
cases (the 60 development cases plus the 120 finished v2 held-out cases). CERMEP, the planned
independent test set, was not read or touched. These are aggregates only, with no case IDs.

## What was tried

| Script | What it does |
|---|---|
| `scripts/dev_m33_skull_improve.py` | Per-vertex comparison of training variants: equal case weights, per-scan normalisation, ico-5 location prior, extra features, a second-pass (cascade) model, a mesh smoothing / clip sweep, 3 mm training copies, and 10–90 % quantile ranges with conformal (CQR) calibration |
| `scripts/dev_m33_skull_features2.py` | Extra MRI-only features per vertex: longer T1 profile, WM–CSF scaled profile, SynthSeg tissue and extracerebral-CSF distance profiles, curvature, distance to the outer skull and scalp, height |
| `scripts/dev_m33_skull_thick.py` | 3 mm thick-slice training copies (random gamma, bias field and noise), rerun through SynthSeg and the watershed |
| `scripts/dev_m33_skull_score_ideas.py` | Full mesh scoring (`score_case`) of the best gradient-boosted combination |
| `scripts/dev_m33_skull_net.py` | 3D U-Net on a 2 mm grid that predicts the signed distance to the CT inner skull, trained on the Mac GPU (MPS); network alone and averaged with the gradient-boosted model ("hybrid") |

They all run as soma-queue phases 6 and 9–19 (`scripts/soma_queue.py`), and `scripts/soma-status` shows
network-training progress.

## Per-vertex proxy (180 cases, median per-case mean |error|, before mesh smoothing)

| Variant | mm |
|---|---|
| v3.x features (base) | 0.88 |
| + equal weights, per-scan normalisation, location prior | 0.88 |
| + extra features | 0.85 |
| + second pass | 0.84 |
| Lighter smoothing (5 iterations, clip 12 mm) instead of 10 / 6 | 0.82 vs 0.87 |
| 3 mm copies, scored on 3 mm inputs | 1.01 vs 1.05 without (no change on 1 mm) |

After calibration, the 10–90 % ranges cover 78–92 % of vertices, depending on the centre.

## Full mesh scoring, inner skull (180 cases)

| Model | Mean abs (mm) | Median | HD95 | Change vs v3.2 (95 % CI) | Cases improved |
|---|---|---|---|---|---|
| v3.2 retrain | 1.41 | 0.94 | 6.77 | – | – |
| Gradient-boosted, training ideas | 1.35 | 0.89 | 6.62 | −0.061 (−0.085, −0.040) | 125 |
| 3D U-Net alone | 1.40 | 0.97 | 6.69 | −0.004 (−0.083, +0.048) | 70 |
| Hybrid (average of the two) | 1.33 | 0.89 | 6.58 | −0.079 (−0.148, −0.035) | 121 |

The improved gradient-boosted model is better than v3.2 at every centre. The network alone is
not. The hybrid's extra gain over the improved model comes almost entirely from centre C, where
its interval crosses zero. Recommendation: carry forward the improved gradient-boosted model.
The remaining error is dominated by a few cases whose starting watershed surface is far off,
and per-vertex correction cannot fix those.
