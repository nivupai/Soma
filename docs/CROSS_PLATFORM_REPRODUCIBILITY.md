# Cross-platform numerical reproducibility

The benchmark soma.synthetic-reproducibility-v1 runs12 deterministic cases using
existing Soma methods and independent references: affine coordinates, RAS/LPS,
nearest labels, analytic cube overlap/brute-force surfel distance, tetrahedron
geometry, SciPy Welch and sine variance, analytic Gaussian-wavelet response,
closed-form diagonal inverse, independent QR GLM effects/contrast variance, and
exact serialization/migration/checksum invariants. No new estimator is introduced.

Every case records observed absolute/relative error, reference scale, tolerance
and its mathematical rationale. Coordinate/OLS tolerances reflect well-conditioned
floating-point operations; Morlet tolerance includes finite five-sigma truncation.
Exact sign flips, integer labels and within-run byte/content invariants are distinct
from tolerance comparisons. No bitwise identity across BLAS implementations is
assumed. Seeded synthetic recovery is not human anatomical/statistical validation.

The CI target matrix is Linux x86_64/ubuntu24.04 and macOS arm64/macos15,
Python3.11/3.12. GitHub's official hosted-runner reference documents macos15 arm64
for private repositories: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
CI asserts actual architecture and records platform/Python/dependencies/numerical
backend information with private synthetic-only artifacts. Actual executed job
conclusions, not configured matrix entries, determine platform evidence. Local
Darwin arm64 results do not stand in for unexecuted macOS CI jobs.

The dependency-floor lane uses a feasible joint intersection, not independently
selected nominal minima: NumPy2.1.0/SciPy1.14.0 (MNE1.13 requirements) and pandas2.3.0
(Nilearn0.14 requirement). Existing scientific dependencies are preserved. Fresh
wheel/sdist/source install checks remain separate from editable development.
Exact resolved manifests, interpreter/architecture and backend versions are
recorded per execution. No universal lockfile promises identical binary execution.
Frontend package-lock and pinned Hatchling/actions remain in force.

Run soma results verify-reproducibility NEW_JSON. Review all errors, not just an
aggregate PASS. GitHub artifacts retain per-platform evidence for14 days; durable
summary evidence and actual limitations belong in MILESTONE17_RESULTS.md/PR checks.
