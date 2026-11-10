# Milestone 17 results addendum

Soma 0.17.0 adds durable scientific result contracts without changing estimators.
The verified baseline was main a096e59819dd3f4955f7f64704941d1ba0c93ecc (940 tests).
Historical reports remain unchanged. This addendum records new execution evidence.

## Contracts and compatibility

The shared soma.result envelope supports 1.0.0 and 1.1.0; new writes use 1.1.0.
Version 1.0.0 is an explicitly constructed compatibility baseline introduced in
this milestone, separate from historical integer core-manifest schema version 1.
Twelve closed result kinds cover EEG spectra/time-frequency/bursts, MRI geometry,
segmentation/surface/registration, source reconstruction, fMRI contrasts/ROI,
experiment manifests and incomplete legacy records. Missing metadata remains
unknown; explicit null means inapplicable. Validation and interpretation are
separate. Future versions, malformed payloads and failed hashes are rejected.

Structured compatibility checks reject different subjects/datasets, incompatible
coordinate frames/grids, axes/sampling/reference conventions, ontologies,
methods/configurations, inverse models, fMRI design/contrasts and estimands.
Missing scientific declarations produce INDETERMINATE. Explicit PSD/TFR power
conversion supports V²/uV²; conversion never silently changes coordinates or
estimands. Checksums detect accidental modification, not malicious authorship.

Four explicitly selected historical fixtures were migrated read-only: the early
synthetic Welch output (one channel, 161 frequency bins), Milestone 6 and 7
verification records and Milestone 16 SDK examples. Numerical values and original
JSON/provenance are preserved. All four remain INDETERMINATE because unrecorded
scientific metadata cannot be recovered. See migration-receipt.json; synthetic
array artifacts remain ignored local outputs. No human artifacts were migrated.

## Executed local gates

- Full Python suite: 1,019 passed, 106 warnings; 79 meaningful schema tests added.
- Offline suite: 1,002 passed, 17 integration tests deselected, 104 warnings.
- Frontend: 18 passed; Playwright: all 10 passed with the explicit local allowlist.
  Demo-only CI deliberately skips the existing local-data browser integration.
- Ruff lint/format and strict mypy: pass (209 source files). TypeScript, ESLint,
  Prettier and production frontend build pass. Existing chunk-size warning remains.
- Pip check passes. Python/npm audits found no known vulnerabilities; the local
  unpublished Soma package itself has no PyPI vulnerability matching record.
- Wheel/sdist contents inspected; repeated builds produce identical hashes.
  Fresh noneditable wheel/sdist/source install receipts and nine public SDK
  examples are verified separately from editable development.
- All 112 baseline test/experiment files are byte-identical. Existing scientific,
  numerical, frontend and browser assertions were preserved.
- Gitleaks 8.30.1 scans proposed files, full sanitized history, reachable blobs and
  commit metadata. No material secrets, restricted data or private home paths;
  only two existing SHA-bound reviewed false positives. No rules were suppressed.
  Raw medical data, local outputs, environment files and credentials stay ignored.

Local Darwin arm64/Python 3.12.2 passes all 12 numerical cases with independent
mathematical/reference implementations. The feasible dependency-floor environment
(NumPy 2.1.0, SciPy 1.14.0, pandas 2.3.0) passes all 79 schema tests and numerical
cases. Frozen tolerances are bundled and hash-bound; they were not widened in
response to observed failures. The CI comparator checks actual outputs across
Linux x86_64/macOS arm64 and Python 3.11/3.12, with twice the per-oracle bounds by
the triangle inequality. Exact input-hash identity is reported separately.
Actual platform evidence is recorded below and in platform-comparison.json.

## Performance and limits

Five-repeat local medians for 1 KiB / 1 MiB payloads respectively: metadata
inspection 0.79 / 0.76 ms; metadata validation 0.42 / 0.39 ms; serialization
28.86 / 25.54 ms; verified loading 1.94 / 3.47 ms; compatibility 0.76 / 0.80 ms;
migration 0.92 / 1.01 ms; provenance input verification 2.55 / 4.71 ms; Explorer
discovery with full integrity verification 7.10 / 8.74 ms. Whole-process peak RSS
was 341.3 MiB; Python allocation peaks reached about 64 MiB because bounded reads
reserve their safety limit. No timing threshold or universal performance claim.
Inspection reads metadata only; loading, provenance checks and Explorer discovery
read all linked bytes. Arrays are read-only snapshots, not lazy memory maps.

Format validity, numerical equivalence, statistical calibration, anatomical
validation and clinical validity remain different claims. No new estimator,
human anatomical validation or clinical readiness is established. Existing fMRI
confirmation gates and source-model limitations remain. Only declared reviewed
legacy adapters are supported; missing fields are never guessed. POSIX Mac/Linux
file handling is tested; Windows support is not claimed. Scanner results cannot
prove absence of every possible sensitive string.

Machine-readable inventory, migration receipts, local numerical errors/environment,
performance and security evidence are in experiments/milestone17. Proposed next
Milestone 18: reviewed workflow-level provenance graphs and cache invalidation,
subject to a separate user-approved scope. It has not been started.

## Executed cross-platform CI addendum

[CI run 42725087662](https://github.com/nivupai/Soma/actions/runs/42725087662)
executed all four required numerical jobs on feature commit 4534b7f. Each passed
all 79 schema tests and all 12 numerical cases. Downloaded reports were inspected
and independently compared locally using the same frozen protocol.

| Actual OS / architecture | Python | NumPy | SciPy |
|---|---|---|---|
| macOS / arm64 | 3.11.9 | 2.4.6 | 1.17.1 |
| macOS / arm64 | 3.12.10 | 2.5.4 | 1.18.1 |
| Linux / x86_64 | 3.11.18 | 2.4.6 | 1.17.1 |
| Linux / x86_64 | 3.12.16 | 2.5.4 | 1.18.1 |

All 36 comparisons against the macOS/Python 3.11 baseline passed, with maximum
observed absolute difference 2.365e-14 (GLM effect). Exact affine, voxel index,
label, GLM image and serialization input hashes agree across all four runs.
Generated EEG values and GLM design input hashes differ; their numerical outputs
still agree within declared tolerances. Thus equivalent generator configuration
and numerical agreement do not imply universal byte-identical inputs.
Linux reports identify single-thread OpenBLAS variants; macOS threadpoolctl
reports OpenMP but does not identify every linked math backend. That observation
is retained without guessing an unreported backend. All reported environments
and per-case differences are in the durable synthetic-only comparison table.

The first CI run caught Prettier formatting in one newly added frontend test.
Prettier was applied without assertion changes and frontend gates rerun. This
formatting correction and this evidence addendum require green CI before merge.
