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

# Milestone 2 verification

Verified locally on 2026-11-06 using the existing Python 3.12.2/macOS ARM64
resolved environment. No new dependencies were required. Soma was reinstalled
editable as `soma-neuro==0.2.0`; `requirements-resolved.txt` still records the
unchanged external dependencies. The 84 Milestone 1 cases and assertions remain
unchanged. Remote CI is configured but has not been executed; nothing is pushed.

| Check | Observed result |
| --- | --- |
| Offline default `pytest -q` | 141 passed, 2 integration tests deselected |
| Unit suite | 85 passed |
| Numerical suite | 56 passed |
| Cached-data integration suite | 2 passed |
| Total executed distinct tests | 143: original 84 plus 59 added |
| Ruff lint and format | Passed |
| Strict mypy | Passed, 28 source files |
| Dependency check | No broken requirements |
| CLI help/list and new command help | Exit 0 |
| Synthetic spectrum regression | Passed through the unchanged existing test and CLI |
| Event-locked synthetic laboratory | Completed, figures/CSV/NPZ/JSON inspected |
| Artifact-injected laboratory | Completed; injected pulse trial rejected |
| Real S001R04 motor imagery | Completed against cached EDF; no additional downloads |

The expanded suite covers event semantics, sample rounding and nonzero first
sample offsets, chronology, overlaps, invalid labels/durations/boundaries,
recording identity, exact half-open windows, rest containment, filter guards,
amplitude and nonfinite rejection, all-trials-rejected outputs, unavailable
references, coordinate alignment, zero/near-zero denominators, template matching,
copy safety, known filtering/phase/drift behavior, Morlet full support, analytical
power scaling, noise, lateralization and run identity. A no-reference plotting
case confirms that an ERD figure is not invented. Multi-run fixture tests cover
4/8/12 identity without fetching extra recordings.

Selected real parameters: 64-channel average reference; 1–40 Hz Butterworth
prototype order 4, SOS, forward-backward zero phase; no notch, ICA, resampling or
explicit global DC subtraction. Calculated boundary guard is 582 samples
(3.6375 s); effective −3 dB crossings approximately 1.104/37.305 Hz. Selected
analysis channels C3/Cz/C4; analysis [1,3), context [0,4); Welch one-second Hann,
50% overlap, 1 Hz bins; Morlet five cycles, 8–30 Hz every 1 Hz, no decimation,
explicit full-support masks. Default normalization uses separately accepted T0
windows within the same run. The executable settings file is
`configs/motor-imagery.json`; METHODS.md gives equations and caveats.

S001R04 events: T0 rest=15, T1 left imagery=8, T2 right imagery=7. Default counts:

| Stage | Proposed | Accepted | Rejected |
| --- | --- | --- | --- |
| Imagery analysis | 15 | 14 (7 left, 7 right) | 1 |
| T0 analysis | 15 | 14 | 1 |
| Imagery TFR context | 15 | 14 | 1 |
| T0 TFR context | 15 | 14 | 1 |
| Proposed matched references | 15 | 14 | 1 |

The final imagery event (index 29, left) overlaps the recording-end filter guard;
the first rest (index 0) and first proposed matched reference overlap the initial
guard. Stage counts refer to different proposal sets: the matched reference for
the final rejected imagery event can itself be valid. Counts of normalized
imagery trials therefore require intersecting the accepted task/reference IDs.
The separate real `matched_rest` CLI run normalized 13 of the 14 accepted imagery
trials (7 left and 6 right); the first right-imagery trial retained absolute power
without an invented reference. No default analysis-window rejections were
attributed to amplitude criteria.
Many unfiltered raw channels have high absolute excursions relative to the
acquisition reference; this is reported without labeling all channels defective.

Descriptive whole-band ERD relative to the selected condition-level rest:

| Channel | Left mu % | Right mu % | Left beta % | Right beta % |
| --- | --- | --- | --- | --- |
| C3 | −31.39 | −64.38 | −25.84 | −30.01 |
| Cz | +39.04 | −22.02 | −2.01 | −25.01 |
| C4 | −34.38 | +15.94 | −19.03 | −3.44 |

These are arithmetic mean trial changes with a shared per-run rest reference.
Mean log ratios differ from logs of mean ratios. TFR figures average normalized
wavelet values and need not equal these Welch band changes. Lower C3 mu power
is observed in right imagery in this run; left-imagery sensor asymmetry is less
pronounced. There is no significance test, population inference, causal claim
or assumption that all subjects show a canonical lateralization pattern.

Synthetic ground truth: 68 seconds, 9 rest annotations and four imagery trials
per hand, 10/20 Hz carriers, amplitude factors 0.5/0.7/0.8 corresponding to
−75/−51/−36% power change. Noiseless unfiltered cases at fs=100/160/256 Hz satisfy
the analytic Welch and time-averaged Morlet assertions. Seed 42 with 0.5 µV noise
and default filtering recovers mean condition changes within 1.010 percentage
points of truth; the largest individual band/trial error is 2.575 points, within
the documented 5-point noisy tolerance. Correct C3/C4 lateralization signs were
recovered. Clean synthetic imagery: 8/8 accepted. Injecting the 1 mV pulse:
7/8 accepted, 1 rejected. Synthetic rest: 7/9 accepted, two recording-edge guard
rejections. Matched reference: 7/8 accepted, one initial guard rejection.

Reports and five figure types were inspected under
`reports/milestone2-review/{synthetic,artifacts,real}/`. Final reports with clean
committed provenance use `reports/milestone2-committed/{synthetic,artifacts,real}/`.
Each contains the requested top-level CSV/JSON reports plus `geometry.json`,
`lateralization.csv`, `report.md`, and `run-04/` scientific NPZ arrays.

Failures encountered and resolved:

- Initial lint/type checks identified immutable default calls, long lines and an
  implicit Matplotlib re-export. Named frozen defaults, formatting and explicit
  imports fixed them without weakening checks.
- Installed MNE deprecated `standard_1005`. Geometry now records and uses the
  current `colin27_1005` name with a legacy fallback for supported older versions.
- An initial new test assumed a constant instantaneous Morlet ratio for mixed
  10/20 Hz tones. Cross-term beating violates that assumption; the test now checks
  temporal mean power against the analytical ratio and retains edge masks.
- An initial 2-point noisy per-trial tolerance was too strict for only three
  overlapping two-second-trial periodograms. The documented 5-point tolerance
  accounts for finite noisy amplitude/reference estimates; noiseless analytical
  assertions remain tight. Observed maximum default-seed error is recorded above.
- A stricter new event length validator initially rejected MNE's NumPy integer
  `n_times`. It now accepts Python and NumPy integer counts without changing
  onset, sample-alignment, identity or overlap checks.
- Figure review exposed PSD autoscaling dominated by attenuated out-of-view
  frequencies. Axes now scale to the displayed 5–35 Hz range; density arrays and
  numerical results are untouched. Timeline legends no longer cover events.

Limitations: only S001R04 and Python 3.12 were verified with real data locally.
Runs 8/12 and Python 3.11 remain supported/configured rather than empirically
verified here. Template locations are not measured geometry. QC thresholds are
operational flags, not artifact diagnoses; channel flags do not automatically
remove channels from the average reference. IIR edge guards are operational,
not guarantees against all ringing or inter-condition smearing. Rest selection,
reference, filtering and rejection choices affect these descriptive results.
No ICA, inferential statistics, source localization, MRI or decoding is included.
Milestone 3 was not started.
