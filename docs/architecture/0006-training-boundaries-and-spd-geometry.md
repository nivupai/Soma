# ADR 0006 — training partitions and SPD geometry

Accepted for Milestone 5. Preserve the validated EEG pipeline and statistical
APIs. Add identified trial tensors with event/window provenance, a bank of
trial-local features/covariances, fresh sklearn pipelines, group-aware nested
selection and separate prospective access.

Use MNE CSP, sklearn covariance/linear classifiers and pyRiemann geometry. Do not
reimplement advanced algorithms to avoid dependencies. Explicitly regularize and
measure SPD matrices, reject zero energy, and distinguish geometry invariance from
properties lost by isotropic shrinkage. No transductive tangent update.

Cache only label-independent trial-local computations. Fit scalers, thresholds,
CSP, tangent references and class means in exact training partitions. Persist
memberships once, link every fit and candidate, preserve numerical failures, and
compute population uncertainty over subjects. Seal prospective choices and input
identity after development validation and before any held-out access. No automatic
held-out download is part of a development command.
