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
