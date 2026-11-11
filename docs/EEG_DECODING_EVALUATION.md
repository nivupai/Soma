# EEG evaluation receipts and independent references

The v22 benchmark uses existing Soma estimators without changing their numerical
assertions. Subject-disjoint source/target roles govern zero-shot transfer;
run-held-out folds govern within-target fitting. Inner source-subject CV selects
parameters separately for each prespecified sensitivity. No outer score chooses
an architecture, channel set, normalization policy or primary configuration.

Private record coverage retains every planned EDF and every QC outcome. Private
M17 cells retain trial IDs, labels, predictions, scores/probabilities, selected
parameters and fit audit. Every target/model/mode remains in the subject table,
including failures. A subject score requires all planned evaluation runs. Aggregate
receipts contain complete/planned/missing counts, equal-subject metrics, confusion
counts, bootstrap intervals, anonymous distribution bins, source selections, cost,
sensitivity and separate adaptation/null diagnostics. `verify_execution` checks
native receipts and every sealed private file hash; it does not certify scientific
independence. `aggregate_export` rechecks current evidence and refuses private rows.

Welch uses volts and a one-second Hann window with half overlap; integrate each
specified frequency band, then log positive power. New tests independently compare
SciPy PSD quadrature, scikit-learn OAS and classification metrics. Existing MNE CSP
transform/eigenspace and Riemannian/SPD invariance/reference tests remain unchanged.
Perturbation tests show target features cannot change training-fitted state. Synthetic
known-mixture CI checks exercise all five methods and both modes. These numerical
checks do not establish that EEG decoding is causal, localized, clinical, robust to
all acquisition shifts, or independently externally replicated.

Full results and historical protocol differences are recorded in
[MILESTONE22_RESULTS.md](MILESTONE22_RESULTS.md). Raw EDFs, per-subject tables,
trial predictions, pseudonym key, private inventory and personal paths are excluded
from Git, distributions and HTTP. Public figures use anonymous aggregate counts;
private participant forests stay local.
