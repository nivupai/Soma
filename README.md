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

Fetch is the only command that downloads. Repeat `--subjects` and `--runs` to
select multiple recordings. `SOMA_DATA_DIR` sets the raw data root. Output
directories must be new: reruns require a different `--output`. Raw EDF and
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
