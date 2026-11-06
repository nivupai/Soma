# Milestone 1 verification

Verified locally on 2026-11-06, Python 3.12.2 on macOS ARM64. The exact installed
distributions are in `requirements-resolved.txt`. Key scientific versions:
NumPy 2.5.4, SciPy 1.18.1, MNE 1.13.2, NeuroDSP 2.3.0, Pandas 2.3.3,
Matplotlib 3.11.2, Typer 0.28.0. Version ranges in `pyproject.toml` permit Python
3.11 and 3.12; only 3.12 was executed locally. GitHub Actions is configured for
both, but remote CI has not been run and nothing was pushed.

Executed successfully:

| Check | Observed result |
| --- | --- |
| Editable installation with development dependencies | `soma-neuro==0.1.0` installed |
| `pytest tests/unit -q` | 43 passed |
| `pytest tests/numerical -q` | 40 passed |
| `pytest -q` | 83 passed, 1 integration test deselected |
| `pytest -m integration tests/integration -q` | 1 passed against cached S001R04 |
| `ruff check .` | All checks passed |
| `ruff format --check .` | All files formatted |
| `mypy src/soma` | No issues in 18 source files |
| `python -m pip check` | No broken requirements |
| `soma --help`, `soma datasets list` | Exit 0, help and registry metadata displayed |
| `soma experiments synthetic-spectrum` | Six signals and all artifacts saved |
| `soma datasets fetch eegmmidb --subjects 1 --runs 4` | Only S001R04 EDF downloaded |
| `soma eeg inspect --subject 1 --run 4` | Sensor/event metadata inspected |
| `soma eeg analyze --subject 1 --run 4` | Motor-channel plots, powers, arrays, manifest and report saved |

Numerical observations from seed 42, 20 s, fs=160 Hz, Hann L=320, overlap=160:

| Signal | Peak (Hz) | Mean square (V²) | Integrated PSD (V²) |
| --- | --- | --- | --- |
| 10 Hz tone | 10 | 5.000000e−11 | 5.000000e−11 |
| 20 Hz tone | 20 | 5.000000e−11 | 5.000000e−11 |
| Combined | 10 (20 Hz also recovered) | 1.000000e−10 | 1.000000e−10 |
| Noisy | 10 | 5.935206e−11 | 5.955566e−11 |
| Modulated | 10 | 5.625000e−11 | 5.520833e−11 |
| Burst | 10 | 1.901525e−11 | 1.965041e−11 |

Tone tests cover fs=100/160/256 Hz and durations 4/10/23 s. Exact rectangular
Parseval, boundary interpolation, Nyquist, frequency spacing, deterministic RNG,
SciPy equivalence, median behavior, invalid dimensions and nonfinite data were
also executed. See MATHEMATICS.md for tolerances and why broadband trapezoidal
integrals are not exact Parseval sums.

S001R04: 20,000 samples (125 s), 64 EEG channels at 160 Hz, 30 annotations
(T0=15, T1=8, T2=7). C3/Cz/C4 are present. Descriptive band powers:

| Channel | Mu 8–13 Hz (V²) | Beta 13–30 Hz (V²) |
| --- | --- | --- |
| C3 | 1.743333e−10 | 1.952042e−10 |
| Cz | 1.558474e−10 | 1.791879e−10 |
| C4 | 1.244004e−10 | 1.435211e−10 |

These summaries combine rest and imagery and include unremoved artifacts. No
statistical significance or left/right inference is claimed.

Figures were rendered and visually inspected: synthetic spectra and six signal
traces; real EEG spectra and a five-second C3/Cz/C4 segment. Initial outputs are
under `reports/synthetic-spectrum/` and `reports/eeg-s001-r04-verified/`. Fresh
post-commit outputs use `reports/committed/synthetic/` and
`reports/committed/eeg/` to include the committed revision. Raw EDF is under
`data/raw/MNE-eegbci-data/files/eegmmidb/1.0.0/S001/S001R04.edf`.
`data/derived/inspection-s001-r04.json` contains the CLI inspection output.

Failures encountered and resolved:

- Default uv cache was outside the writable workspace; relocated to `/private/tmp`.
- Restricted network prevented initial installation; authorized network access
  installed dependencies and fetched only the requested EDF.
- Initial mypy identified a missing list annotation and dynamic NPZ keyword
  typing. Fixed with an explicit path-list type and a named density matrix schema.
- The first real report failed JSON serialization of MNE's NumPy integer sample
  count. It is now converted to a Python int; regression is covered by the real
  integration test. The incomplete `reports/eeg-s001-r04/` directory was retained
  and a new output path used, honoring the no-overwrite policy.
- Initial font-cache warnings were resolved with writable explicit cache paths;
  package plot defaults are now inside `data/derived/.cache`.

Remaining limitations: local verification covers one Python/platform environment
and one real recording. Dependency ranges are not an exhaustive compatibility
claim. Third-party typing remains partial. No preprocessing, measured montage,
epoching, uncertainty estimation, source reconstruction or MRI computation is
implemented. Failed multi-file analyses can leave partial outputs; reruns need a
new directory. MNE's download cache is reused, not independently authenticated
against a publisher checksum. Full workflow and scope are in ROADMAP.md.
