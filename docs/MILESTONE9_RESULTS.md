# Milestone 9 results — Soma 0.9.0

Local baseline is e7cf639 with 461 unchanged tests. The frozen
[reliability protocol](MODEL_RELIABILITY_PROTOCOL.md) and
[initial diagnostic audit](../experiments/milestone9/initial-audit.json) preceded
new algorithms. Old M8 reports remain byte-identical. The original coregistration
and 21-case uncertainty workflows reproduced before numerical additions.

## Main findings

* Large real fiducial discrepancies compare measured head points with MNI-derived
  MRI proxies. They are not independent anatomical errors. Soma and supported
  MNE equal-weight fitting agree near machine precision; headshape fits optimize
  different scalp/initialization objectives. No real anatomical truth was invented.
* Historical −98.967% RMS current bias is a valid A m ratio at the true vertex.
  Its dominant explanation is resolution gain 0.0102446. Noise-free W L predictions
  agree with direct reconstruction near 1e-15. No amplitude metric was relabeled
  as fixed or silently replaced by dimensionless statistics.
* Ninety full MNE estimator/orientation/depth/regularization settings produced
  270 source metrics; the MNE-only resolution study has 30 settings/90 rows.
  Lower lambda did not remove severe attenuation. dSPM/sLORETA remain normalized
  statistics, with separate localization/pattern evidence and no physical bias claim.
* Asymmetric-phantom Gaussian held-out coverage is 92%, 98%, 94% across 100 trials
  per noise model; bad initialization yields about 44.4-mm held-out TRE. All 100
  incorrect full-rank correspondence controls are rejected.
* Supplied MRI derivative comparisons show substantive discrepancies and cannot
  independently validate anatomy. Overall readiness stays INDETERMINATE.
* Forty paired noise draws across 17 settings expose factor interactions. Error
  is not exactly additive; assumptions are not measured biological variation.
* A post-protocol diagnostic finds 104 sources within 5 mm of an inner-skull
  triangle despite the MNE nearest-vertex distance setting. The shallowest is
  0.676 mm away. The historical source space is preserved and the limitation is
  [documented separately](MODEL_RELIABILITY_ADDITIONAL_FINDINGS.md).

## Artifacts and reproducibility

Final reports are local under `reports/milestone9-validated/{coreg,inverse,resolution,
evidence,uncertainty}`. Every figure has an NPZ companion. Manifests bind recursive
output hashes, seed, environment, Git state and exact Python source-tree SHA256.
Runs preceding the local release commit retain their then-dirty Git revision;
the source-tree hash binds the executed implementation. The compact
[verification receipt](../experiments/milestone9/verification.json) preserves actual
checks, metrics, caches, source/asset identities and timings.

Run `sh experiments/milestone9/run.sh reports/my-reliability-run` with the existing
sample cache and M8 report arrays. No data download is implicit. M8 historical
arrays are required for the historical metric audit; missingness fails explicitly,
without fabricating a replacement. Ordinary tests are offline; actual BEM/MNE
integration is opt-in. Existing M6–8 integration workflows and public contracts
remain unchanged. No new runtime dependencies or segmentation algorithm were added.

See [coregistration](COREGISTRATION_AUDIT.md), [inverse calibration](INVERSE_CALIBRATION.md),
[anatomical evidence](ANATOMICAL_EVIDENCE.md) and [attribution](UNCERTAINTY_ATTRIBUTION.md)
for definitions, numerical values and interpretation. Single-subject, on-grid
synthetic results do not establish anatomical registration accuracy, unbiased
currents, population performance or clinical validity.

A proposed Milestone 10 is prospective validation against independent participant
MRI landmarks and tissue-boundary references, under a separate dataset/protocol,
including source-clearance and off-grid reconstruction comparisons. It has not
been started. Nothing is pushed remotely.

## Executed acceptance

All 495 tests passed, including 34 additions; original tests and all 98 M8 report
files are unchanged. Ruff/formatting/strict mypy/dependency checks pass. Eighteen
figures were inspected; 58 output hashes and 208 saved arrays were validated.
Final wall times are 5.03/5.49/3.73/8.93/3.81 seconds for coregistration/inverse/
resolution/evidence/attribution, respectively. Peak process RSS ranges 419–772 MiB.
These cache-aware local profiles are documented with environment and CPU-stage
metrics in the verification receipt, not presented as general performance limits.
