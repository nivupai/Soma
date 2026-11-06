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
