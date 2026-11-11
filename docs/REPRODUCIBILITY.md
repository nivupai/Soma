# Reproducibility

Install with Python 3.11 or 3.12 in a virtual environment and `pip install -e
'.[dev]'`. `requirements-resolved.txt` records the actual verified Python 3.12
macOS environment, excluding the editable project path. To reproduce versions,
install that file then install the project editable. Platform-specific wheels
and Python versions can still affect results. CI tests both supported Python
versions using declared compatibility ranges; the local resolved file is an
execution record rather than a universal cross-platform lock.

Every experiment creates a new directory with `exist_ok=False`. Existing output
is never silently reused or replaced, even after a failed run. Choose a fresh
output path. Failures can leave an incomplete directory; a successful run has
its report and manifest. No atomic multi-file transaction is promised.

Manifests contain source dataset/version/file, subject/run (null for synthetic),
scientific parameters, sampling frequency, selected channels, PSD conventions,
units, random seed, execution UTC timestamp, Python and installed library
versions, application version, Git revision and working-tree state when available.
Machine paths are isolated under `paths`. EEG manifests include a SHA-256 of the
original EDF. This is identity tracking, not verification against a remote signed
checksum. Raw files remain unchanged; derived arrays and summaries are separate.

Synthetic signals use a fresh `numpy.random.default_rng(seed)` for each generator
call. The six-signal experiment uses the same seed intentionally, so noisy and
burst cases share the background realization. Exact bitwise random results are
only promised for the recorded compatible environment, not arbitrary future
NumPy versions. Determinism tests compare repeated calls within that environment.

`spectra.npz` holds `frequencies` (Hz, shape F), `density` (V²/Hz, shape C×F), and
`channels` (Unicode labels, shape C). Load with `numpy.load(..., allow_pickle=False)`.
CSV powers are V² and retain full numeric precision. PNG is presentation only;
never extract quantitative results from a log-axis plot. `recording.json` retains
EDF event samples and annotation durations; manifests retain estimator settings.

Offline tests use short synthetic arrays and mocked MNE loading. They cannot
prove that a live server, a changed EDF, or every future third-party release is
compatible. `pytest -m integration tests/integration` is opt-in and reads only an
already cached S001R04 file, skipping if absent. CI never fetches EEG files.

Git revision is null if no commit exists, or if a wheel installation is outside a
repository. Dirty state is explicit. Initial pre-commit verification artifacts
can therefore record a null revision; post-commit verification should use fresh
output directories to record the committed revision. Generated files are ignored.

Spectral PNGs show 0–40 Hz (or the available range if smaller) and six decades
below the largest plotted density. This display limit hides numerical roundoff
near pure-tone zero bins; the saved NPZ density arrays are untouched.

## Milestone 2 artifact schema

`configs/motor-imagery.json` is an executable CLI configuration. Defaults and all
actual overrides, sampling rates, Welch and Morlet settings, reference floors,
QC thresholds, channels and run identities are included in each manifest. The
existing library/version/Git/seed tracking remains unchanged. Source EDF hashes
are retained, and arrays are derived without rewriting EDFs. Runs 4/8/12 require
explicit prior fetch; analysis never downloads recordings.

Top-level tables retain `subject`, `run`, `recording` and annotation/trial indices:

- `events.csv`: original code, semantic label, onset, duration and sample.
- `trials.csv`: every proposal by stage, acceptance, exact half-open sample range,
  reference event identity and rejection reasons.
- `spectral_features.csv`: accepted trial/channel/band powers and valid reference,
  percent/log/difference normalization. Unavailable numeric values are empty CSV
  cells; counts distinguish unavailable normalization from absent trials.
- `condition_summary.csv`: per-run means, sample SD and normalized counts.
- `lateralization.csv`: per-trial C4-minus-C3 over sum, with defined sign.
- `quality.json`: channel metrics, every proposed trial's detailed QC and counts.
- `preprocessing.json`: actual settings, SOS coefficients, measured response,
  phase, group delay, edge guard and channel policy.
- `geometry.json`: coordinates, frame, units, montage name and template caveat.

Each `run-XX/spectra.npz` stores density T×C×F, frequency/channel/trial/condition
coordinates, rest density and rest trial indices, and T×C×band reference powers.
`run-XX/timefrequency.npz` stores wavelet power T×C×F×time, explicit coordinates,
full-support masks, half-support widths, band trajectories, aligned reference
power, percent/log/difference arrays, validity mask, condition-mean power and
condition trial counts. Band order is explicitly stored. Load with
`allow_pickle=False`. NaNs in arrays are explicit unsupported or undefined
quantities, not nonfinite raw samples passed through the analysis.

Plots can be disabled without suppressing scientific artifacts. When no supported
wavelet reference exists, `erd_ers.png` is omitted and normalization is masked.
Some conditions can have valid absolute results but no normalized results. Longer
context and short analysis windows have separate logs; their counts can differ.
Noisy synthetic references use the recorded seed; filtering and QC settings must
be held constant when comparing runs. Multi-run summaries retain each run rather
than treating trials as independent population observations.

## Milestone 3 cohort and sensitivity execution

YAML/JSON describes subjects/runs and scientific settings; data/cache/output paths
are separate CLI arguments. `configs/cohort.yaml` selects 1–5×4/8/12 and seed 42
for statistics. `configs/sensitivity.yaml` names all ten predefined variants.
Repeat `--subjects` and `--runs` for Typer lists; cohort analysis never downloads.
The existing explicit fetch command requests only a selected Cartesian product.

Each new output directory is exclusive. Deterministic experiment IDs include
canonical scientific settings, relevant software identity and ordered requested
record fingerprints (or explicit unavailability markers); sensitivity IDs include
the constituent experiment IDs. Reordering the same selections does not change
identity. Different inputs/configurations do not overwrite one another.

Run cache keys contain original EDF SHA-256 (or a seeded synthetic source
identity), recording/subject/run, all motor/burst settings, installed scientific
versions, Python version, architecture/byte order, application version and a
source-code digest. Statistical/plot settings are excluded from the numerical
run cache, but retained in experiment provenance. Changing statistics alone can
reuse run artifacts; changing numerical settings invalidates them. Development
source changes invalidate caches even before a version bump. Source hashing is
conservative and can invalidate caches for changes unrelated to a particular
estimator; no premature layered preprocessing cache is claimed.

Caches contain CSV, JSON, numeric NPY/NPZ and checksums, never pickle. Publication
uses a staging directory and rename. Every cache read verifies artifacts; corrupt
or incomplete cache entries are reported as failed records, not silently trusted
or overwritten. Remove or relocate a corrupt cache explicitly before retrying.
Output copies do not share writable table files with the cache. Full selected
continuous arrays are cached once; cohort outputs retain compact summaries,
coordinates and time-averaged TFRs rather than duplicating full trial TFR volumes.
The Milestone 2 command remains available for complete trial×channel×frequency×time
artifacts.

Top-level cohort artifacts:

- `coverage.csv/json`: every requested record, errors, fingerprints, cache status,
  stage counts and timing; no external exclusion list is applied.
- `events.csv`, `trials.csv`, `features.csv`, `summary.csv`: original run/trial
  identities, rejected proposals, spectral features and descriptive run summaries.
- `run_contrasts.csv`, `subject_contrasts.csv`, `population.csv`: paired-run and
  subject estimands, effective n, run SD, nominal subject-bootstrap CIs.
- `leave_one_subject_out.csv`: subject exclusion sensitivity, not a deletion policy.
- `lateralization*.csv`: explicit absolute/log sensor conventions and uncertainty.
- `burst_features.csv`, `burst_events.csv`, `burst_dynamics.csv`: exposure-aware
  trial features, censored fragments and 100 ms event-relative bins.
- `burst_condition_summary.csv`, `burst_*contrasts.csv`, `burst_population.csv`:
  exposure-weighted within-run and equal-subject paired summaries.
- `burst_power_contrasts.csv`, `burst_power_associations.csv`: aligned descriptive
  subject associations, with missingness and effective n.
- `retention.csv`, `profiling.csv`, `manifest.json`, `report.md` and saved figures.

Per-subject/run metadata retains template coordinates, preprocessing response,
QC details, thresholds, source identity and profiling. `tfr_mean.npz` contains
`mean_over_valid_time` (trial×channel×frequency), trial labels/indices, frequencies,
channels, and the original time/support coordinates; it is not a full TFR volume.
Failures can leave incomplete output directories, as in earlier milestones.

Sensitivity tables retain each configuration, aggregate and matched-subject
changes, sign consistency, relative changes, retained trials/subjects, missing
references and burst effects. Near-zero primary denominators can make relative
changes unstable; use absolute changes and explicit retention first. No best
configuration is selected. Cached compute timing in a warm run describes its
original miss; `elapsed_seconds` and cache status describe the current attempt.

Benchmarks save hardware/software context, cold/warm and sweep wall costs,
per-run TFR costs, exact array footprints, tracemalloc peaks and process high-water
RSS. Native allocations may not all appear in tracemalloc; RSS is not a per-stage
memory delta. No absolute-time thresholds run in CI. Separate 200-replication
normal-subject coverage experiments at n=40 and n=5 expose the limitations of
nominal percentile intervals; their results are not replaced by a favorable seed.


## Milestone 4 protocol and execution

The frozen protocol's canonical SHA-256 is
`9995060c58ffb3a896d725ef9641f27fb7645950b76fbbf59b6ee97f3488ab61`.
`configs/replication-freeze.json` also seals the document and raw configuration
bytes, timestamped before fetching new subjects. Do not edit these artifacts;
a scientifically revised protocol requires a separately named analysis.
Explicit subset overrides are recorded as deviations from the frozen cohort.

Replicate and calibrate support `--resume`. Reuse requires matching code,
environment and parameters. Replication rechecks source fingerprints and per-run
artifact checksums, preserves failed attempts, and atomically rewrites progress.
Calibration validates chunk checksums and derives separate deterministic data
and inference streams. Both publish new immutable aggregation generations.
Interrupted publication cannot turn a half-written chunk into a valid checkpoint.
Concurrent writers to the same output/cache key are unsupported.

Local outputs: `reports/m4-replication-main`, `reports/m4-sensitivity-main`,
`reports/m4-reference-audit-main`, `reports/m4-calibration-main`; their manifests,
CSV tables and figures contain provenance. Reports/data remain Git-ignored;
`docs/MILESTONE4_RESULTS.md` preserves compact scientific findings in Git.
Early development manifests honestly identify a dirty v0.3.0 parent tree;
post-commit calibration and freshly generated replication/audit reports
record the clean v0.4.0 revision without rewriting the original experiment.
The exact development sweep source is preserved as a checksummed archive at
`reports/m4-execution-source`; final edge-case aggregation corrections do not
change successful-record scientific computations. Final outputs are under
`reports/milestone4-committed/`. Calibration's scientific code digest remains
independent of unrelated report/CLI edits.

The final sensitivity report recomputes robustness and figures from the completed
900-analysis saved sweep. Its manifest hashes all input tables, the original
scientific manifest and exact-source archive. It explicitly records this as
saved-table aggregation, rather than claiming a second raw-data sweep. The
self-contained `reaggregate.py` is retained alongside that report.


## Milestone 5 decoding identities

`configs/decoding.yaml`, its SHA-256 and `decoding-freeze.json` seal the narrative
and machine protocol before training. Initial canonical SHA-256:
`11912588d1457a334580eab3fa1093367a762ee94c0157ed6d71cdaa849547bf`.
Do not edit the sealed narrative or configuration to reflect observed outcomes.
The later `decoding-frozen.yaml` stores the full initial protocol, final
source/dependency identity, development input fingerprint, candidate scores and
selected parameters, validation receipt hash and timestamp before prospective
fetch/read. The held-out command verifies all of those applicable boundaries
before creating its access-start receipt and explicitly requested fetch.

Decode manifests include sklearn/pyRiemann/threadpoolctl versions as well as the
existing numerical dependencies. Cache records include EDF hashes, exact settings,
code identity, retained trial IDs/arrays and artifact checksums. Predictions,
metrics_run/subject, comparisons, influence, selection, partitions, gzipped fits,
fitted states and profiling are machine-readable. No fitted supervised
transformation is reused across training partitions. Figure inputs are saved;
sensor pattern maps declare template geometry and arbitrary pattern units.

Final development outputs live at `reports/m5-development-final` (the initial
run is preserved at `reports/m5-development`), synthetic results at
`reports/m5-synthetic-verified`, and measured stages at `reports/m5-benchmark-verified`.
An exact development-start source archive documents the single Ruff-only shortening
of an unused held-out receipt message during development; executed numerical
methods and all protocol decisions remained unchanged. Prospective code is frozen
after the completed development and current-code validation, not during that edit.


The completed prospective report is `reports/m5-heldout`. Freeze commit `a6b458f`
precedes its access-start receipt and all EDF downloads. Every prospective model
manifest identifies that clean commit and the unchanged frozen source identity.
The final reporting commit changes documentation only. Frozen configurations
remain immutable, with false `heldout_accessed` denoting their creation-time
snapshot; completion/access state is in the report receipts. Reproducing the
same fixed run is not a fresh prospective validation.

`audit.json` and `audit_reproduction.py` verify all source/target EDF hashes and
recorded fit memberships. `metrics_model.csv` gives equal-subject/run metric
summaries derived from per-run data, and `figure_captions.md` gives sample counts
and uncertainty for the saved figures. `environment.json` includes numerical
software and thread-pool information. Raw EDFs, caches and bulky reports remain
Git-ignored; compact results and sealed configurations are committed.


## Source-modeling reproduction

The source protocol receipt binds the original Markdown and YAML SHA256 before
real analysis. `source-*.sha256` seal canonical JSON configurations. Source
commands require explicit asset fetching; tests never fetch fsaverage. Use the
README source commands with a new output directory and bounded BLAS threads.
`geometry.npz` supplies source vertices and head coordinates for all figure arrays;
`forward.json` binds montage, transforms, BEM conductivities and anatomical hashes.
Native FIF/source caches have staged publication and checksum completion receipts.
Result manifests bind the full source tree, parameters, seeds, libraries, Git
revision/dirty state and file checksums. Real results retain raw EDF hashes,
trial/QC logs, rest covariance FIFs, trial-wise vertex powers, ROI features,
equal-run maps and units. Synthetic results retain every case's truth metadata,
training/evaluation seed distinction, operators and numerical recovery tables.
Selected resolution arrays retain PSFs, CTFs and separate geodesic distances.

Run `pytest` for offline CI, and `pytest -o addopts=''` for explicitly cached
integration tests. No anatomy/raw data or large result arrays are committed.
The v0.6.0 implementation was exercised before its feature commit; manifests
honestly record the baseline Git revision plus a dirty tree and exact source
hash. A later commit does not retroactively alter those receipts. Local report
paths and measured performance are listed in SOURCE_MODELING_VALIDATION.md.


## MRI experiments and provenance

Use configs/mri-geometry.yaml and new output paths. The MRI plan records initial
acceptance criteria and explicitly records the added continuous-sphere control
after binary-mask area bias was observed; no preregistered success is invented.
Synthetic seed 42, analytic transforms/landmarks, optimizer traces, inverse
consistency, threshold references and mesh measurements are retained. Real data
have an anatomy-only HTTP-range receipt with official URL, member name, ETag,
terms and SHA256. No functional series or raw anatomical image is committed.

MRI manifests include parameters, input metadata/checksums, complete source-tree
hash, software versions, Git revision/dirty state, runtime/CPU/RSS and result
hashes. Transform subdirectories contain native SimpleITK and RAS-m receipts;
figure companions contain numerical arrays. The exact verified source identity,
artifacts, tests and performance are in MRI_VALIDATION.md and the small committed
experiments/milestone7/verification.json. Reports were produced before the feature
commit and honestly retain the parent revision plus dirty state.

Ordinary pytest is offline. Full cached integration is `pytest -o addopts=''`;
tests never fetch MRI/anatomy. A real experiment without --fetch requires the
verified local cache. For bounded profiling, set OPENBLAS_NUM_THREADS=1 and
ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1. Benchmark lazy/eager memory in isolated
processes; process high-water RSS is not an incremental stage allocation.

## Reliability studies (v0.9.0)

`configs/model-reliability-freeze.json` binds the protocol and four prospective
YAML files. Old M8 report hashes are captured in the initial diagnostic audit and
verified after the new work. Named `SeedSequence([42, stream_id])` streams isolate
registration scenarios, training covariance, electrode geometry and evaluation
noise. Common evaluation draws pair perturbation/factorial cells; intervals use
independent draws within each setting, not cells as independent participants.

Inverse caches bind actual forward arrays/basis/source IDs, covariance, projector
state, channels, method, orientation, depth, lambda, code and versions. Changed
physical inputs invalidate the corresponding stage; corrupt/incomplete caches fail.
Every final report records the source-tree hash in addition to Git revision/dirty
state, recursive output hashes, wall/CPU time and process high-water RSS. See the
Milestone 9 receipt and run script. Reports and large public assets remain ignored;
committed receipts do not imply the historical report arrays are bundled in Git.

## Independent-reference study (v0.10.0)

The M10 protocol/five YAML files have a pre-analysis checksum receipt. Raw BrainWeb
and Mindboggle downloads preserve formats, licenses/source documents, selection,
transport bytes, paths and SHA256. The first invalid empty BrainWeb response is
quarantined; it was never used in scoring. Explicit header/label casts are recorded.
Old reports and all baseline tests are checked byte-for-byte against their receipts.

Continuous-source/operator caches bind actual source/sensor coordinates, physical
conductor parameters, transforms, code and MNE/NumPy/SciPy versions. Returned native
source identities are checked. Common seed streams pair all source/grid/solver/
lambda comparisons. Manifests and supplemental analysis bind exact source/data/code
hashes; output directories are exclusive. Report assumptions, cache state and
process RSS scope when reproducing timings. Data licenses and transport containers
are not a promise that the whole reference distribution is bundled with the code.


## Milestone 11

M11's protocol/config seal is configs/milestone11-freeze.json. It precedes reference
scoring and held-out label inspection. IBSR registered access prevented actual
human evaluation; no post-hoc subject substitution is presented as prospective.
SCI archives/selected members are pinned in experiments/milestone11/external-discovery.json;
fetch_sci.py explicitly verifies or retrieves only those resources. run.sh executes
all six CLI actions offline after acquisition into a new root, with one worker.
AnatomyReport fingerprints source tree, package version, outputs and runtime/RSS.
M11 numerical reports are reports/milestone11-final; earlier attempts remain
separate. The verification receipt preserves all 42 earlier test-file hashes and
168 prior report-file hashes. The user-authorized one-line version expectation
update to 0.11.0 is recorded separately with its before/after test-file hashes;
the other 41 baseline test files are byte-identical. Source code and scientific
reports are unchanged by this verification correction.


## Milestone 11 human MRI integration addendum

The new seal configs/human-tissues-freeze.json precedes scoring, and the new
protocol is docs/MILESTONE11_HUMAN_PROTOCOL.md. Data discovery, exact input hashes,
archive member checks, geometry and phase outputs are local ignored artifacts.
`experiments/milestone11-human/run.py` executes inventory, development, a source/
input binding freeze and external evaluation with one worker and exclusive output
roots. `reports/milestone11-human-validated` is the final reviewed run. Earlier
new attempts and all historical reports remain distinct. Commit only generic code,
policy and aggregate verification; individual data hashes/paths, per-subject metrics,
MRI pictures and prediction files remain private local report artifacts. Frozen
models are unchanged between development and external scoring. No network access,
weight download, test-label payload read, remote push or Milestone 12 is required.

## Milestone 12 addendum: MRI execution and immutable derivatives

Use configs/mri-pipeline.yaml and configs/pipeline-benchmark.yaml with the sealed
ADR/config hashes in configs/milestone12-freeze.json. Private manifests bind input
content/geometry, source tree, software, transforms, backend and parameters.
Explicit resume verifies final output hashes; compatible new-output runs reuse
stages. Corrupt committed caches require explicit quarantine/rebuild. Never write
into original MRI roots or publish individual output receipts. See
[recovery semantics](PIPELINE_REPRODUCIBILITY.md) and the
[experiment commands](../experiments/milestone12/README.md). The full test command
retains the one user-directed historical version assertion failure; all other
cases pass. M11 outputs and original tests are byte-identical.

## Milestone 13 addendum: frozen task models

The fMRI protocol/configs and separate SPM input amendment are sealed before real
model outcomes. Actual archive/input hashes, event origins, model parameters,
software/source identity and output hashes stay in private reports. No raw BIDS
image is implicitly preprocessed; SPM's raw educational exception is explicit.
Only supported masks enter standardized derivatives, while statistics/design/QC
are custom reports. Full-report verified reuse is distinct from resumable fitting;
changed content/config/source or corrupted products fail closed. Default CI remains
offline; optional human data are never fetched in pytest. See
[commands/Python use](../experiments/milestone13/README.md) and
[results](MILESTONE13_RESULTS.md). No original test/report was rewritten.

## Milestone14 addendum: sealed calibration and staged human access

configs/milestone14-freeze.json seals the original protocol; the separate validation
amendment seals fresh seeds15142–15241 without changing models/thresholds. Exactly
one ds000114 raw pilot was fetched with annex/SHA verification; no cohort expansion
or external preprocessing ran. Audit identity includes source files, inherited
metadata, transforms/reference grids, confounds, code and reviewed evidence.
Stale pilot outputs or inputs cannot authorize cohort reuse. Clinical inputs and
individual outputs remain ignored. See [commands](../experiments/milestone14/README.md)
and [measured results](MILESTONE14_RESULTS.md). Human-data gaps are not filled by
raw fitting or by simulated subjects. Historical results remain byte-identical.

## Milestone 14.1 addendum

Protocol/config freeze: `configs/milestone141-freeze.json`. Final inference
policy/evidence/source freeze before attempted human analysis:
`configs/milestone141-policy-freeze.json`. Scripts, environment/command details
and aggregate result receipt: `experiments/milestone141/README.md`.
Independent SeedSequence streams use seed1411000; exact historical repetition
uses15142–15241. Do not mix repeated historical seeds with new validation.

Ignored synthetic reports preserve exact X/c, temporal/spatial covariance,
estimator diagnostics, individual realizations, probability/plot arrays, versions,
source hashes, runtime/RSS and output hashes. Private raw inventories preserve
MRI acquisition metadata and source hashes. The aggregate audit exports no
individual medical hashes or paths. Image25.2.7 is pinned by registry digest;
metadata-only inspection does not establish local availability or executed
software. No human derivative/transform chain was produced. Reproduction and
new-source hash algorithms are documented explicitly rather than equated.
Existing output directories must be preserved and fresh runs named separately.

## Milestone15 addendum

Explorer demo reuses seeded Soma generators; no private data are required.
The frontend lockfile pins its dependency tree and project-local supported Node
runtime. Python service versions are recorded in the aggregate performance and
verification receipts. Install dependencies/browser separately; ordinary
scientific, component and synthetic E2E tests do not fetch datasets.

Run `python -m experiments.milestone15.benchmark` from the repository root for
bounded in-process API timings. Optional ignored local configuration is created
by `python -m experiments.milestone15.configure_local` only for the existing
permitted cache. `BENCHMARK_EXPLORER=1` records synthetic browser measurements;
`CAPTURE_EXPLORER=1` deliberately refreshes synthetic screenshots during Playwright.
Private job manifests and participant imagery stay ignored. Original reports are
read-only and their checksum ledger is verified before commit. Setup and exact
commands are in `EXPLORER_USER_GUIDE.md`.

## Versioned artifact reproducibility

See CROSS_PLATFORM_REPRODUCIBILITY.md and RESULT_SCHEMA_SPECIFICATION.md. File-byte
identity, logical dataset identity, backend/environment identity and tolerance-based
numerical equivalence are separate records. Unsupported schema/method semantics
require a named adapter or recomputation. Never use private old filesystem paths
as required reproducibility inputs.

## Workflow replay (Milestone 18)

Exact-environment cache identities bind declared semantics and observed dependencies.
Resume revalidates schemas, linked bytes, producer versions and lineage. Four real
synthetic DAG replays accompany the unchanged M17 numerical oracles on supported
platforms. Numerical equivalence does not authorize cache interchange. See
WORKFLOW_REPLAY.md, WORKFLOW_RECOVERY.md and WORKFLOW_CI.md.

## Research protocol replay (0.19.0 addendum)

Frozen scientific identity differs from execution/cache identity. Actual four-platform
CI runs compare protocol fingerprints, environment evidence, selected numerical
outputs, artifact content and existing schema oracles. M19 uses unchanged frozen
bounds; numerical agreement does not prove biological validity or authorize cache
interchange. Local sealing is not independent preregistration, and repeated runs
are not automatically a human longitudinal study. See the seven protocol guides.

## Human identity/evidence (0.20.0 addendum)

Four actual CI environments check deterministic fictional identity serialization,
dataset-scoped pseudonyms, permissions, frozen cohorts, registration schema and
synthetic lineage. CI requires no human data and makes no claim of equivalent real
access across platforms. Existing M17/M18/M19 numerical checks remain mandatory.
Human pilot records stay local, bind actual input hashes and permissions, and are
not automatically prospective, confirmatory or longitudinal biological evidence.

## Milestone 21 addendum

M21 retains the macOS arm64/Linux x86_64 Python 3.11/3.12 matrix and existing numerical tolerances. Each runner executes offline synthetic readiness tests and emits fictional canonical-bundle/session/registration/gate invariants for exact comparison. This cannot establish equivalent real human data access or validated longitudinal results.

## v0.22 decoding evaluation

The locally sealed `configs/eeg-benchmark-v22.json` binds the complete cached EEG
inventory fingerprint before target fitting. M18 verifies preprocessing cache
content/code/environment; M17 stores each fold/model and aggregate receipt. The
runner refuses changed cohort/code/permission/environment during resumption.
Private predictions, subject tables, EDF hashes and FitAudit membership stay in
ignored reports. Public exports contain aggregate statistics and SVG figures only.
No human-data CI download is required. See `EEG_BENCHMARK_PROTOCOL.md` and
`MILESTONE22_RESULTS.md` for historical reuse and actual local execution evidence.

The four actual CI runners retain macOS arm64/Linux x86_64 and Python3.11/3.12.
`eeg_benchmark_repro.py` emits known-mixture synthetic outcomes; the comparison
requires all four artifacts and exact declared invariants. These checks do not
establish cross-platform human-data replication or permit cache interchange.
