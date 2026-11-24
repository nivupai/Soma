# Soma

Soma (`soma-neuro`, v0.32.0) is a research Python toolkit for computational
neuroscience: EEG signal analysis and decoding, structural MRI geometry and tissue
segmentation, EEG forward/inverse source modeling (BEM and FEM head conductors),
task-fMRI GLMs, and the provenance machinery around them (versioned result schemas,
sealed protocols, cached workflow DAGs and replay). It ships a `soma` CLI, a Python
SDK, and an optional local web workstation, **Soma Explorer**.

## What Soma does and does not claim

Soma is a **research prototype**. It is not a medical device and makes no clinical claim.

- **Numerical solvers are validated on synthetic heads only.** BEM, FEM, mesh and
  inverse code is checked against analytical references and frozen synthetic
  multi-shell studies, including the failures. See the results for
  [M27](docs/MILESTONE27_RESULTS.md), [M28](docs/MILESTONE28_RESULTS.md),
  [M29](docs/MILESTONE29_RESULTS.md), [M30](docs/MILESTONE30_RESULTS.md) and
  [M31](docs/MILESTONE31_RESULTS.md).
- **Human anatomy is NOT validated.** Each anatomical head model gets a readiness
  label: `VALIDATED`, `QC_ONLY` or `NOT_READY`. At v0.32.0 **zero heads are
  `VALIDATED`**. One MNE-sample conductor is `QC_ONLY`, and the 23 IBSR/MRBrainS
  segmentation cases are `NOT_READY` as complete head conductors
  ([M32 results](docs/MILESTONE32_RESULTS.md)).
- Human source-localization accuracy, skull/scalp conductor truth and physical
  phantom validation have not been established. Commands keep missing evidence
  visible as blocked or indeterminate records and never fill it in.
- No command downloads data unless you pass an explicit `fetch` subcommand or a
  `--fetch` flag. Raw medical data never belongs in Git. See the
  [data policy](docs/DATA_POLICY.md).

## Install

You need **Python 3.11 or 3.12**. `requires-python = ">=3.11,<3.13"`, so pip
refuses to install Soma on Python 3.13 or later.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'          # editable install from a checkout
```

Optional extras (see `pyproject.toml`):

| Extra | Adds | Needed for |
|---|---|---|
| `conductor` | `openmeeg==2.6.0` | OpenMEEG BEM forward solves |
| `fem` | `scikit-fem==12.0.2` | independent P1 FEM reference |
| `mesher` | `gmsh==4.15.2` | independent Gmsh volume meshes |
| `explorer` | FastAPI, Pydantic, Uvicorn, httpx | Soma Explorer API |
| `dev` | pytest, ruff, mypy, stubs, BIDS validator, build | tests and linting |

CI installs everything with `pip install '.[dev,explorer,conductor,fem,mesher]'`.
`requirements-resolved.txt` pins the exact verified environment. More detail:
[SDK installation](docs/SDK_INSTALLATION.md).

## Quick start

All of these commands run offline on synthetic data. Output directories must not
already exist.

```bash
soma --help
soma datasets list                                   # dataset metadata, no download
soma experiments synthetic-spectrum --output reports/synthetic-spectrum
soma experiments event-locked --seed 42 --output reports/event-locked
soma mri experiment synthetic --seed 42 --output reports/mri-synthetic
soma fmri simulate --seed 13042 --output reports/fmri-synthetic
python -m examples.eeg_analysis                      # one of the SDK examples
```

From Python:

```python
from soma.signal.synthetic import synthetic
from soma.signal.spectral import welch, WelchConfig

signal = synthetic("sine10", seed=42)
spectrum = welch(signal, WelchConfig(nperseg=320, noverlap=160))
print(spectrum.peak_frequency, spectrum.band_power(8, 13))  # 10.0 ...
```

To work with real EEG, fetch an explicit selection first. This is the only step
that downloads anything:

```bash
soma datasets fetch eegmmidb --subjects 1 --runs 4 --data-dir data/raw
soma eeg analyze --subject 1 --run 4 --data-dir data/raw --output reports/eeg-s001-r04
```

The [SDK examples](examples/README.md) list every runnable example. The
[milestone history](docs/MILESTONES.md) has the full per-milestone command
reference.

### Soma Explorer (optional, local only)

```bash
python -m pip install -e '.[dev,explorer]'
npm --prefix apps/explorer ci
python -m uvicorn services.explorer_api.app:app --host 127.0.0.1 --port 8000
npm --prefix apps/explorer run dev                   # second terminal
```

Open `http://127.0.0.1:5173`. The default demo is synthetic and every view is
marked SYNTHETIC/EXPLORATORY. Never bind to `0.0.0.0`. See the
[Explorer user guide](docs/EXPLORER_USER_GUIDE.md) and
[security notes](docs/EXPLORER_SECURITY.md).

## Architecture map

`src/soma/` holds the Python package. The `soma` CLI entry point is `soma.cli:app`.

| Area | Packages |
|---|---|
| Core and provenance | `core` (paths, hashing, signal arrays), `results` (versioned schemas, migration), `workflow` (cached DAGs, invalidation, replay), `protocol` (sealed protocols, amendments) |
| EEG | `signal` (synthetic signals, Welch, bursts), `eeg` (events, epochs, ERD/ERS), `decoding` (CSP and Riemannian decoders), `eeg_benchmark`, `external_eeg`, `model_archive` (pickle-free fitted models) |
| Statistics | `statistics`, `simulations` (calibration), `reliability` |
| Imaging | `imaging` (NIfTI, registration, segmentation, surfaces), `pipeline` (BIDS MRI DAG and derivatives), `geometry` (frames, coregistration, electrodes), `fmri` (GLM, preprocessing audits, retest) |
| Head models and sources | `anatomy` (MRI-derived head models, conductor QC), `source` (forward, inverse, BEM/FEM references, priors, uncertainty), `validation` (tissue and conductor benchmarks) |
| Data and governance | `datasets` (explicit fetch adapters and registries), `human` (identity, permissions, readiness gates) |
| Interfaces | `cli.py`, `sdk` (public Python API), `experiments` (reproducible studies), `visualization`, `benchmarks`, `resources` (packaged synthetic artifacts) |

Explorer has two parts. `services/explorer_api/` is a FastAPI service that serves
reviewed, hash-checked artifacts read-only. `apps/explorer/` is the React and
TypeScript frontend (Vite, three.js, React Flow), and `src/features/` holds one view
per domain: EEG, MRI, Source, fMRI, Workflows, Protocols, Data Audit, BEM/FEM,
mesh grid, inverse calibration and human head models. Configs are in `configs/`,
frozen study inputs and public synthetic outputs are in `experiments/`, and helper
scripts are in `scripts/`.

## Documentation

All documentation lives in [`docs/`](docs/). Good starting points:

- [Architecture](docs/ARCHITECTURE.md), [mathematics](docs/MATHEMATICS.md),
  [methods](docs/METHODS.md) and [decision records](docs/architecture/)
- [SDK overview](docs/SDK_OVERVIEW.md) and [API reference](docs/SDK_API_REFERENCE.md)
- [Datasets](docs/DATASETS.md) and [data policy](docs/DATA_POLICY.md)
- [Reproducibility](docs/REPRODUCIBILITY.md), [verification](docs/VERIFICATION.md)
  and [roadmap](docs/ROADMAP.md)
- [Milestone history](docs/MILESTONES.md), the `docs/MILESTONE*_RESULTS.md` reports,
  and [CHANGELOG.md](CHANGELOG.md)

## Running tests

```bash
pytest                         # full offline suite; integration tests are deselected
pytest tests/unit tests/numerical
ruff check .
ruff format --check .
mypy --strict src/soma services
python -m scripts.run_sdk_examples --output reports/examples.json
# Opt-in, needs data you fetched yourself; never downloads:
pytest -m integration tests/integration
```

Explorer frontend:
`npm --prefix apps/explorer run typecheck && npm --prefix apps/explorer test`.

## License

License: not yet chosen. Until the owner picks one, no license is granted beyond
what applicable law allows. Third-party datasets keep their own terms, listed in
[docs/DATA_POLICY.md](docs/DATA_POLICY.md).
