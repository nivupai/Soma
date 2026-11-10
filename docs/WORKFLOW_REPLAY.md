# Workflow replay and numerical equivalence

Run `python scripts/replay_workflows.py --cache NEW_CACHE --output NEW_JSON`.
The harness executes EEG, MRI, fMRI and source DAGs cold, warm and after a scientific
parameter change. It records stage keys, observed content and per-file hashes,
software/environment, cache observations, limitations and numerical summaries.
It also reruns all 12 established Milestone 17 analytical/reference oracles.

The EEG stages validate two voltage channels, use the existing rereference and
Welch functions, and integrate mu/beta bands. MRI uses a fixed noisy 16³ intensity
phantom, geometry validation, existing one-iteration N4, threshold foreground
segmentation, QC and surface extraction. The phantom is not human ground truth;
foreground segmentation does not certify brain tissues, skull/scalp or BEM.
Source stages use the existing three-dimensional Tikhonov/resolution toy.

fMRI uses existing synthetic BOLD, metadata validation, design and Nilearn-backed
Soma OLS fitting. The numeric cache stores theta, covariance, dispersion, residual
DOF, design and diagnostics. Contrasts reconstruct only supported Nilearn OLS
statistics and call its Tcontrast; no model is refitted, no executable object is
pickled, and no residual data are fabricated for estimation. A zero-column shape
placeholder supplies acquisition count to the constructor only. Numerical tests
compare effect and variance against Soma's existing full contrast path at 1e-12.
ROI reporting is descriptive; no confirmatory p-value/rejection workflow is exposed.

Frozen tolerances live in bundled workflow-tolerances-v1.json, hash-bound in reports:
EEG atol1e-23/rtol1e-10 for tiny spectral powers; MRI physical-volume atol1e-18 m³/
rtol1e-12 for floating-point determinant/summation; fMRI atol1e-9/rtol1e-8 for
well-conditioned GLM summaries; toy inverse atol1e-14/rtol1e-13. Across runs the
comparator uses twice these bounds by the triangle inequality. M17 per-oracle
bounds remain unchanged. Tolerances do not certify scientific validity.

CI executes the existing Linux x86_64/macOS arm64 × Python3.11/3.12 matrix, verifies
actual architecture and uploads synthetic-only reports. A separate comparison
checks all four actual reports and their frozen protocol. Configured jobs are not
execution evidence; actual conclusions belong in the results addendum.
Logical identities, exact input/output content and file bytes are reported
separately from numerical agreement. Differences in dependency versions can
change logical identities; exact environment policy always governs cache reuse.
Numerical agreement alone never authorizes cross-platform cache interchange.
