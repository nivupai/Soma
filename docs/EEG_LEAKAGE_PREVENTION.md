# EEG fitting and leakage boundaries

Source-only grouped selection never reads target labels/features to choose a
parameter. Zero-shot scaler parameters, CSP spatial filters, MDM class means and
tangent reference means are fitted on source training data only. Within-subject
models fit on the other two runs, using source-selected parameters. Fixed filtering,
referencing, Welch PSD and OAS/Ledoit–Wolf **per-trial** covariance construction are
feature definitions, not target-population fitting. Per-trial shrinkage depends on
that trial, just as its power spectrum does; no collection of target covariances
sets a reference. Tangent-space test-reference updating stays disabled.

Every fit retains existing FitAudit train/test trial membership. Tests perturb
all target features and verify training-only scaler/CSP/MDM/tangent state remains
unchanged. Tests also cover subject/run overlap, inner target membership, incorrect
class labels, adaptation contamination, missing subjects, protocol mutation and
corrupted native receipts. Existing independent MNE CSP and covariance tests are
preserved; new tests compare PSD integration with SciPy, OAS with scikit-learn and
metrics with independent scikit-learn calculations. Numerical parity establishes
implementation behavior, not biological validity.

Target-supervised adaptation uses the earliest balanced 0/4/8 labeled accepted
run-4 trials and tests only runs8/12. Every calibration count uses the same test
IDs. Insufficient calibration labels create failures, never a smaller undocumented
calibration size. Adaptation is labeled separately and cannot establish zero-shot
transfer performance.

M18 preprocessing caches verify code, parameters, environment and actual EDF hashes;
permission is rechecked before cache reuse. M17 cells bind dataset, labels, fold,
selected parameters, protocol and software. M19 seals bind the plan before execution.
Changing source during a run aborts publication; changed inventory or environment
refuses an incompatible resumed execution. Native receipt/hash verification is
integrity evidence, not proof of independent preregistration or consent.
