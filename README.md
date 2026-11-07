# Soma

Research-oriented scientific Python foundations for EEG analysis. Milestone 1
provides explicit EEGBCI ingestion, validated one-dimensional signal arrays,
NeuroDSP Welch spectra, absolute mu/beta power, and reproducible experiments.
No MRI or source localization implementations are included.

Python 3.11–3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
soma --help
soma datasets list
soma experiments synthetic-spectrum --output reports/synthetic-spectrum
soma datasets fetch eegmmidb --subjects 1 --runs 4 --data-dir data/raw
soma eeg inspect --subject 1 --run 4 --data-dir data/raw
soma eeg analyze --subject 1 --run 4 --data-dir data/raw --output reports/eeg-s001-r04
```

Downloads require `datasets fetch` or the explicit `eeg replicate --fetch` flag. Repeat `--subjects` and `--runs` to
select multiple recordings. `SOMA_DATA_DIR` sets the raw data root. Output
directories must be new except resumable replication/calibration with `--resume`. Raw EDF and
reports are excluded from Git. `requirements-resolved.txt` captures the verified
environment; use it in addition to the editable install for exact versions.

```python
from soma.signal.synthetic import synthetic
from soma.signal.spectral import welch, WelchConfig

signal = synthetic("sine10", seed=42)
spectrum = welch(signal, WelchConfig(nperseg=320, noverlap=160))
print(spectrum.peak_frequency, spectrum.band_power(8, 13))
```

Validation:

```bash
pytest tests/unit
pytest tests/numerical
ruff check .
ruff format --check .
mypy src/soma
# Explicitly uses an already downloaded recording; no automatic network:
pytest -m integration tests/integration
```

See [architecture](docs/ARCHITECTURE.md), [mathematics](docs/MATHEMATICS.md),
[datasets](docs/DATASETS.md), [reproducibility](docs/REPRODUCIBILITY.md),
[verification](docs/VERIFICATION.md), and [roadmap](docs/ROADMAP.md).

## Milestone 2: event-based motor imagery

The existing Milestone 1 APIs and commands remain available. The new pipeline
adds copy-safe continuous filtering, explicit referencing, template geometry,
run-aware events with durations, logged trial rejection, valid-rest references,
trial Welch PSDs, Morlet power with support masks, and descriptive ERD/ERS.

```bash
soma eeg motor-imagery --subject 1 --runs 4 --output reports/motor-imagery-s1
# Only recordings explicitly fetched by you are loaded; this command never downloads.
soma eeg motor-imagery --subject 1 --runs 4 --runs 8 --runs 12 --output reports/motor-imagery-multi
soma eeg motor-imagery --subject 1 --runs 4 --baseline matched_rest --output reports/matched-rest
soma eeg motor-imagery --subject 1 --runs 4 --baseline none --no-plots --output reports/absolute
soma eeg motor-imagery --subject 1 --runs 4 --config configs/motor-imagery.json --output reports/configured
soma experiments event-locked --seed 42 --output reports/event-locked
soma experiments event-locked --seed 42 --artifacts --output reports/event-locked-artifacts
```

Defaults: 64-channel average reference, continuous 1–40 Hz Butterworth SOS
forward-backward filter, no notch/ICA, [1,3) s analysis, [0,4) s TFR context,
separately identified T0 rest references. The synthetic model uses no rereference
to preserve its known three-channel ground truth. All numerical settings can be
specified with the JSON configuration; unknown fields fail clearly. `--baseline`
and `--reference` override the JSON. `--no-plots` produces scientific artifacts
without importing the new plotting module.

Outputs include events/trials CSVs, QC/filter/geometry JSON, spectral features,
condition summaries, lateralization, run-specific NPZs, provenance and a report.
Figures show event timeline, template sensors, PSDs, TFR and supported ERD/ERS.
No reference is fabricated when unavailable. Runs are never silently pooled.
See [scientific methods](docs/METHODS.md) before interpreting normalized power.

## Milestone 3: cohorts, bursts and robustness

Soma 0.3.0 adds cached multi-subject replication, continuous NeuroDSP bursts,
subject-level resampling, predefined sensitivity designs and profiling. Read the
[research protocol](docs/PROTOCOL.md), particularly the small-cohort uncertainty
limitations, before interpreting estimates.

Typer lists use repeated options:

```bash
# Explicit download selection; no analysis command downloads data:
soma datasets fetch eegmmidb --subjects 1 --subjects 2 --subjects 3 --subjects 4 --subjects 5 --runs 4 --runs 8 --runs 12
soma eeg cohort --subjects 1 --subjects 2 --subjects 3 --subjects 4 --subjects 5 --runs 4 --runs 8 --runs 12 --config configs/cohort.yaml --output reports/my-cohort
soma eeg sensitivity --config configs/sensitivity.yaml --output reports/my-sensitivity
soma eeg bursts --subject 1 --runs 4 --runs 8 --runs 12 --output reports/my-bursts
soma experiments cohort-synthetic --seed 42 --output reports/my-synthetic-cohort
soma experiments cohort-synthetic --seed 42 --missing --artifacts --output reports/my-incomplete-synthetic
soma experiments benchmark --output reports/my-benchmark
soma experiments uncertainty-validation --n-subjects 5 --repetitions 200 --output reports/my-coverage
```

`--data-dir` and `--cache-dir` configure machine paths. Cohort/burst/synthetic
commands accept `--no-plots`; YAML can also set `plots: false`. Outputs must be
new directories. Cache reuse verifies checksums and input/software identity.
Partial completion is explicit JSON plus coverage tables; no successful records
returns failure. Existing Milestone 1/2 commands and APIs remain available.

Cohort figures are drawn from saved tables: subject effects, run consistency,
lateralization, burst occupancy/durations, nominal subject-bootstrap forest
intervals and retention. Sensitivity adds effect-change and missingness figures.
A nominal 95% percentile interval is not a guarantee at five subjects: the
recorded normal simulation covered only 80.5% at n=5. No population significance
or causal burst-mechanism claim is made.


## Milestone 4 — replication and statistical calibration (v0.4.0)

The [sealed research protocol](docs/REPLICATION_PROTOCOL.md) was frozen before
fetching subjects 6–35. Its checksum and timestamped freeze receipt live beside
`configs/replication.yaml`. Primary effects are equal-subject left-minus-right
mean log powers, with at least two paired runs and prespecified t intervals.
Initial-five-informed hypotheses remain exploratory.

```bash
# Uses cached EDFs; repeat --runs rather than space-separated values.
soma eeg replicate --subjects 6:35 --runs 4 --runs 8 --runs 12 --output reports/replication
soma eeg replicate --subjects 6:35 --runs 4 --runs 8 --runs 12 --output reports/replication --resume
soma eeg replicate --sensitivity --output reports/replication-sensitivity
soma eeg audit-reference --subjects 1:5 --output reports/reference-audit
soma stats calibrate --config configs/calibration.yaml --workers 4 --output reports/calibration
soma stats calibrate --config configs/calibration-smoke.yaml --workers 2 --output reports/calibration-smoke
soma stats influence --input reports/replication --output reports/influence
# Explicit expansion only; fetching is a separate opt-in:
# soma eeg replicate --subjects all --expand-all --fetch --output reports/expanded
```

`current.json` points to an immutable aggregation generation. Completed record
checkpoints and Monte Carlo chunks are checksum-validated on resume. Parameter,
source code or environment mismatches reject reuse. Incomplete/failed recording
attempts retain their identities and errors. No command implicitly fetches all
109 subjects. Original EDFs and original M1–M3 outputs remain intact.

See [statistical methodology](docs/STATISTICS.md),
[Milestone 4 results](docs/MILESTONE4_RESULTS.md), and
[verification](docs/VERIFICATION.md). All figures derive from saved CSV tables.
