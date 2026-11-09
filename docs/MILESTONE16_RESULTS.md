# Milestone 16 results — local verification addendum

Soma v0.16.0 stabilizes the explicit `soma.sdk` namespaces, installable local
Explorer gateway, result semantics and private-repository release verification.
It introduces no new neuroimaging experiment or human validation claim. All 106
pre-existing test/experiment files are byte-identical to the sanitized baseline.
The 892 existing tests remain intact; 48 SDK/package tests are added.

## Executed local checks

Local platform: Darwin arm64, Python 3.12.2,
frontend Node v22.23.4, npm 10.8.3. Full exact dependency versions are
in `experiments/milestone16/environment.json`. Linux Python3.11/3.12 results are
separate GitHub Actions evidence; local macOS success is not a substitute for them.

| Check | Actual result |
|---|---|
| Full Python selection | 940 passed, 0 skipped, 105 warnings |
| Offline selection | 923 passed, 17 integration tests explicitly deselected, 103 warnings |
| Frontend | 14 passed |
| Playwright | 8 passed, including actual configured local adapters |
| CLI compatibility | all 13 documented checks passed |
| Synthetic public-SDK examples | all 8 executed |
| Ruff / format | passed |
| Strict mypy | 201 source files passed |
| TypeScript / frontend lint / format / production build | passed |
| pip check / Python vulnerability audit | passed / zero known vulnerabilities |
| npm audit | zero findings after scoped development-dependency remediation |

No scientific or numerical assertion was weakened. New boundary tests exercise
unit/frame/subject/ontology incompatibilities, metadata serialization, reproducible
numerical quantities, inference-policy enforcement and optional Explorer failures.
Artifact privacy negative tests reject medical files, secret files and private paths.

## Installable artifacts and Explorer

Wheel, source distribution and noneditable source installations were each tested
in separate fresh environments. Each checks core first, then Explorer extras,
installed imports/metadata/CLI, all eight examples, API probes and dependency
consistency from an unrelated cwd. Additional fresh wheel, sdist and source
installations passed with index access disabled using a private wheelhouse.
The isolated sdist/source builds also obtain Hatchling from that wheelhouse.
Two fixed-timestamp builds produced byte-identical wheels and source archives.
Reviewed package-content listings/hashes and resolved environment receipts remain
in ignored `reports/milestone16/`; datasets and local artifacts are excluded.

The existing E2E suite exposed a real wheel packaging gap: a checkout-relative
synthetic calibration receipt was absent in installed use. The gateway now reads
an exact synthetic-only excerpt as a package resource, retaining the original
receipt/protocol hashes. A regression checks its values against the unchanged
historical record. Installed smoke checks include the experiment list and export.
All eight E2E tests then passed against the noneditable wheel API launched outside
the checkout, including actual registered EEG/MRI/source/descriptive fMRI artifacts.
Synthetic MRI and experiment-browser captures were visually inspected and retained
only in ignored reports. The lazy Three.js viewer and scientific warnings remain.

## Scientific example outputs

These are deterministic synthetic checks, not human tissue/anatomical validation:

- 2 mm MRI spacing; voxel/world roundtrip error 1.78e-15 voxels.
- Independently thresholded noisy radial intensity vs analytic sphere truth:
  Dice 0.900508, Jaccard 0.819022, ASSD 1.103803 mm, HD95 2.828427 mm,
  signed volume error -1488 mm³. Truth labels never enter prediction.
- Closed tetrahedron Euler characteristic 2, enclosed volume 1.666667e-7 m³.
- Synthetic EEG 10 Hz peak, mu power 8e-12 V²; burst intervals retain half-open indices.
- Identity toy inverse lambda2=.1 gives resolution diagonal 0.909091.
- Synthetic fMRI opposite-region effects +3.03247 and -2.93912, residual dof 96;
  confirmation remains false. Provenance roundtrips strict JSON.

Machine-readable outputs: `experiments/milestone16/examples.json`.

## Measured performance

Five warm repetitions per operation; median milliseconds. Baseline is the existing
implementation on identical synthetic inputs in the same process. Shared engines
and sequential measurements mean small differences are timing variation, not
algorithmic speedups. No timing threshold is enforced in CI.

| Operation | SDK ms | Implementation ms | SDK serialized bytes |
|---|---:|---:|---:|
| MRI_metadata | 0.965 | 1.098 | 547 |
| geometry_check | 0.010 | 0.010 | 19 |
| segmentation_metrics | 9.138 | 5.965 | 2717 |
| EEG_PSD | 0.226 | 0.118 | 4739 |
| surface_QC | 0.387 | 0.556 | 1131 |
| synthetic_GLM | 9.678 | 9.080 | 7410 |
| provenance_read | 0.022 | 0.019 | 44 |

Cold imports: root 0.0012 s,
imaging 0.493 s,
EEG 1.568 s,
fMRI 2.057 s.
Installed loopback Explorer catalog ready in 2.365 s.
Whole-process high-water RSS 260.8 MiB includes imports
and preceding analyses; it is not per-call allocation. Vite reported 301 ms dev
startup and unchanged main/source chunks of 267.69/527.41 kB (gzip84.04/133.14 kB).
The source-chunk warning remains; no bundle-size improvement is claimed.
Machine-readable timings, response sizes and versions are in performance.json.

## Security and CI

Full reachable blobs, historical tree paths/messages, current files and package
members are inspected. Gitleaks8.30.1 runs unchanged standard rules, with no
suppressed rules or scanner allow-comments. Two baseline generic-api-key matches
are reviewed false positives: a public archive filename and a performance receipt
SHA256. Their exact complete-file hashes bind the review; any changed/new finding
fails. Raw scanner exit1 is retained and explained, never described as zero raw
findings. Six previously reviewed synthetic screenshots are content-hash-bound;
other binaries fail the repository gate. No material secret, personal home path,
restricted scan/recording or model weight was found. Scanners cannot prove absence
of every possible sensitive datum; file/content review complements them.

The Node audit initially reported seven moderate findings from the development-only
minimatch dependency. A narrowly scoped typescript-estree minimatch11 override,
compatible with the supported Node runtime, cleared the audit; lint/build/tests
were rerun. Python auditing was explicitly bound to the sanitized interpreter.
The Python audit checked 112 third-party packages; the private, unregistered
`soma-neuro` package has no PyPI advisory entry and is explicitly skipped by that
database lookup. Source/artifact checks cover it separately.
No private-history import or history rewrite was performed.

The first Milestone16 Linux scientific runs exposed additional installed-package
assumptions: frozen protocol documents were looked up relative to site-packages,
and MRI output guards used the package location rather than the destination's
repository. Captured help also contained forced ANSI styles that split option
names. Exact unchanged replication/decoding protocol documents are now packaged,
while source runs still check the actual source documents for tampering. Output
guards find the destination's nearest Soma source tree or Git worktree, preserving
strict ignored-directory policies. Standard NO_COLOR/TERM=dumb settings make CI
help capture deterministic. Three new regressions cover the corrections, and the
entire noneditable installed offline suite passes 923 tests without dependency
skips when the documented developer validator is installed. Without that optional
validator, schema status correctly remains INDETERMINATE; it is not forced to PASS.
Version smoke tests compare with the current project metadata rather than a fixed
release literal. No original test or scientific assertion was modified.

The baseline GitHub run failed strict typing on Python3.11 NumPy stubs; explicit
float64 returns/Python scalar boundaries correct those reports without changing
formulas. CI now separates quality, scientific3.11/3.12, distributions3.11/3.12,
Explorer and security jobs. Official action refs are immutable and permissions
are read-only. Only ordinary push/PR triggers are used, with no secrets injected,
public deployment, PyPI publishing or visibility changes. Merge is conditional
on all final PR jobs succeeding; the PR checks provide authoritative remote status.

## Scientific and distribution limits

The SDK wraps existing methods; it does not certify external preprocessing,
participant coregistration, independent skull/scalp segmentation, conductivities,
BEM anatomy or localization accuracy. Tissue segmentation metrics cannot fill
those gaps. Human and feasible-AR fMRI remain descriptive, ROI uncertainty lacks
a spatial-covariance model, and synthetic numerical checks are not human validation.
Existing experiment orchestrators remain internal/research APIs that may require
repository configuration and explicit permitted local caches. No cross-platform
universal lock, public distribution right or clinical readiness is claimed.
Warnings from upstream libraries, explicit NIfTI unit overrides and the Vite chunk
size remain recorded. Milestone17 is not started.
