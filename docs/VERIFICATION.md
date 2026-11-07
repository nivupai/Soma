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

# Milestone 3 verification

Executed locally on 2026-11-06 with Soma 0.3.0, Python 3.12.2, macOS 15.7 ARM64,
10 logical CPUs. External scientific versions remain those recorded above;
PyYAML 6.0.3 and types-PyYAML 6.0.12.20261103 were added for declarative configs.
`requirements-resolved.txt` was refreshed, and editable installation completed.
Only Python 3.12 was run locally; configured Python 3.11/3.12 remote CI was not
executed and nothing was pushed.

| Check | Observed result |
| --- | --- |
| Default offline suite | 202 passed, 3 integration cases deselected |
| Unit suite | 133 passed |
| Numerical suite | 69 passed |
| Cached-data integration suite | 3 passed |
| Distinct tests | 205: original 143 unchanged, 62 added |
| Ruff lint / format | Passed |
| Strict mypy | Passed, 39 source files |
| Dependency check | No broken requirements |
| CLI help and existing behavior | Passed regression suite and smoke commands |
| Full synthetic cohort | 15/15 records completed |
| Synthetic missing/artifact cohort | 15/15 records completed with explicit missing/rejected trials |
| Real subject 1, runs 4/8/12 | 3/3 completed |
| Real subjects 1–5, runs 4/8/12 | 15/15 completed |
| Ten-configuration real sensitivity sweep | 150/150 record/configuration analyses completed |
| Cold/warm cache benchmark and three-variant sweep | Completed |
| Repeated normal-subject coverage | 200 independent replications each at n=40 and n=5 |

No original test assertion was deleted or weakened. Added tests cover strict
selection/configuration, record identity, repeated-measures grouping, uneven
trial counts, missing conditions, bootstrap determinism and effective n,
scale-invariant exact sign flips, Holm correction, fixed channel references,
invalid/empty inputs, physical threshold calibration, occupancy/duration/count
interventions, noise sensitivity, censoring/exposure, event bins, individual
synthetic effects, missing events/artifacts, cache reuse/invalidation/corruption,
partial/all-missing cohorts, channel mismatches and sampling inconsistency.

## Dataset coverage and retention

Only the requested 15 EDFs were fetched or reused: S001–S005, each R04/R08/R12.
All fetch attempts succeeded, recorded in
`data/derived/milestone3-download-attempts.json`. All loaded files validated as
64 EEG at 160 Hz. No outside exclusion list, other runs or expanded 1–10 cohort
was used. The adapter and cohort compatibility checks were retained unchanged
where appropriate; deliberate invalid-channel/sampling fixtures verify failures.

Primary annotations: 225 rest, 113 left-imagery, 112 right-imagery. Primary
imagery retention: 210/225 (93.33%), all five subjects with three paired runs.
Every run retained 14/15 imagery windows. The 15 rejections were recording-end
filter-guard overlaps, not default amplitude flags. Rest 210/225, imagery TFR
context 210/225, rest TFR context 210/225, matched-reference proposals 210/225.
Reference availability must intersect accepted imagery and reference identities;
proposal counts alone are not normalized-trial counts.

Primary settings: average reference over all 64 EEG, 1–40 Hz continuous
Butterworth SOS forward/backward, no notch/ICA/resampling, C3/Cz/C4 analysis,
[1,3) s half-open power windows, [0,4) s TFR context, same-run accepted T0
reference, one-second Hann Welch / 50% overlap, five-cycle 8–30 Hz Morlet with
support masks. Default broad-filter guard: 582 samples, 3.6375 s. Every run saves
actual geometry, response, QC and source fingerprint. Template head coordinates
remain distinct from measured digitization.

## Real descriptive effects and uncertainty

Primary contrast is left-minus-right mean log absolute trial power, paired in
run, equally averaged over runs within subject, then equally over subjects.
Natural log ratios and nominal 95% pointwise percentile subject-bootstrap intervals:

| Sensor/band | Mean contrast | Nominal interval | Effective subjects |
| --- | --- | --- | --- |
| C3 mu | +0.134851 | [−0.073409, +0.343110] | 5 |
| C4 mu | −0.187216 | [−0.225190, −0.142448] | 5 |
| C3 beta | +0.054245 | [−0.064034, +0.172524] | 5 |
| C4 beta | −0.045273 | [−0.110623, +0.020076] | 5 |

C4 mu subject means were negative for 5/5 subjects and 12/15 run contrasts.
C3 mu was positive for 3/5 subject means and 8/15 run contrasts. These are
observed consistency counts, not population significance or uniform physiology.
Subject estimates, run SDs, leave-one-subject-out results, lateralization variants
and burst CIs are saved separately. Sign flips were disabled in the primary
cohort; at five subjects their exact two-sided minimum p is 0.0625 even with
unanimous signs. No uncorrected multiple-location inference is made.

**Small-n uncertainty limitation:** 200 repeated independent normal-subject
simulations gave coverage 187/200=93.5% at n=40 (exact binomial 95% interval
[89.14%,96.49%]), but 161/200=80.5% at n=5 ([74.32%,85.75%]). Nominal percentile
intervals at five subjects are therefore not calibrated 95% evidence. This
limitation is stated in the protocol, reports and nominal forest labels; the
negative C4 interval is not reported as a significant population finding.

## Sensitivity findings

All ten configurations and all five subjects are retained in the design. They
are not ranked to select a favored result. Actual imagery counts:

| Variant | Accepted / 225 |
| --- | --- |
| Primary | 210 |
| Acquisition reference | 197 |
| Fz/Pz pair reference | 210 |
| 0.5–40 Hz | 195 |
| 1–45 Hz | 210 |
| No power normalization | 210 |
| Matched rest | 210 |
| Strict QC | 193 |
| Permissive QC | 210 |
| Dual high threshold 2.5× rest median | 210 |

C3 mu mean contrast changed from +0.134851 to −0.102075 with acquisition reference,
and to +0.029485 with Fz/Pz. C4 mu remained negative: −0.230782 acquisition,
−0.142662 Fz/Pz. The 0.5 Hz high-pass produced +0.101107 C3 / −0.176636 C4;
strict QC +0.128703 / −0.222747. Raising low-pass 40→45 Hz changed these mu
contrasts by less than 2×10^−7 log units. These are descriptive sensitivity
results and include induced changes in accepted trials. Matched-subject change
and sign consistency are also saved to distinguish membership from mean changes.

Absolute log contrasts were unchanged by normalization choice or the burst-only
threshold change, as expected with unchanged accepted spectral trials. No
normalization intentionally leaves 100% of normalized feature cells unavailable.
Matched rest leaves 90/1260=7.14% unavailable; strict QC leaves 36/1158=3.11%.
No missing reference was filled with an epsilon or invented interval.

## Burst results and synthetic validation

Detection used continuous NeuroDSP seven-cycle FIR/Hilbert processing with
rest-dual median multiples (1,2) and rest percentiles (75%,95%); minimum duration
three cycles at the lower band edge. Guards add preprocessing support, half FIR
support and two seconds of Hilbert guard. Threshold volts, reference exposure,
FIR coefficients, observed event bins and censored fragments are saved.

Illustrative equal-run/channel descriptions over C3/C4 (within-run occupancy
and rates first use actual exposure):

| Strategy/band | Rest occupancy | Left occupancy | Right occupancy |
| --- | --- | --- | --- |
| Rest dual, mu | 19.38% | 15.97% | 16.79% |
| Rest dual, beta | 6.77% | 3.56% | 3.81% |
| Rest percentile, mu | 5.89% | 4.70% | 4.37% |
| Rest percentile, beta | 1.07% | 0.40% | 0.80% |

Rest-dual mu onset rates were about 0.312/s rest, 0.239/s left, 0.264/s right;
beta 0.212/s, 0.114/s, 0.109/s. Complete-duration means were around 0.57–0.62 s
for mu and 0.30 s for beta; censored fragments are excluded and missing means
are not zeros. These threshold-dependent observations do not establish that
changes in burst occurrence causally explain power changes. Subject-level
burst–power associations and effective pair counts are saved, not promoted to
inferential correlations.

Changing the rest-dual high threshold 2→2.5 reduced the C3 mu left-minus-right
occupancy contrast from +0.023620 to +0.004786, illustrating definition sensitivity.
The alternative percentile strategy also yields markedly fewer events. Raw
threshold crossings are not assumed independent physiological events.

The synthetic cohort completed all 15 records with 120/120 imagery windows.
The missing/artifact variant had 114 proposed imagery windows (six explicitly
omitted annotations), 105 accepted and nine pulse-related rejections. Rest
retention was 105/135 in both, with recording-boundary guards logged. Individual
baselines/effects persist across runs, while run/trial variability and noise are
seeded independently. No-reference simulated C3 effects recovered known individual
log-power targets within the predeclared 0.2-log-unit tolerance; the population
mean error stayed below 0.1. Average-referenced noisy truth is not asserted to
retain an unreferenced analytical effect.

Controlled pulse-train tests recovered burst counts for amplitude, shorter and
fewer-burst manipulations; mean-square ratios matched 0.36, 0.5 and 1/3 within
0.001, accounting for a small fixed floor. Hilbert boundary recovery uses a
cycle-based tolerance, not sample-exact ground truth. Increasing noise changed
detections without changing true intervals. Monte Carlo coverage validation is
separate from these deterministic/single-seed numerical regressions.

## Profiling and artifact inspection

The recorded benchmark on this hardware: four synthetic records cold cache
2.731 s, warm cache 0.289 s (0→4 hits); three-variant sensitivity subset 1.757 s.
Mean original-miss TFR computation about 0.0847 s; maximum traced peak about
24.02 MiB for the seven-channel synthetic model. A separate initial 15-record
real run averaged about 0.773 s per record, with ~49.44 MiB traced peak and
~0.122 s TFR stage. Timings are execution observations, not performance guarantees
or CI assertions. Real 64-channel referenced continuous arrays occupy ~9.77 MiB;
three selected channels ~0.458 MiB. Exact arrays and TFR footprints are recorded
in profiling.csv. Process high-water RSS is cumulative, not per-stage delta;
tracemalloc can miss some native allocations.

Figures were rendered from their saved CSV data and visually inspected: subject
effects, run consistency, C3/C4 lateralization, occupancy, complete durations,
nominal forest intervals, accepted/proposed retention, sensitivity heatmap and
reference missingness. Retention labels use contrasting text and include requested
missing subjects/runs rather than silently omitting failed rows. All plotted
values and sample counts can be reconstructed from the adjacent tables.

Initial complete review artifacts: `reports/m3-review/{cohort,subject1-bursts,
synthetic,synthetic-missing-artifacts,benchmark,coverage40,coverage5}/` and
`reports/m3-sensitivity-review/`. Final committed-provenance outputs use
`reports/milestone3-committed/` with the same named experiment subdirectories.
Caches and raw EDFs are ignored by Git; no raw data were committed.

## Failures, fixes and remaining limits

- New static checks caught Pandas scalar-union typing, tuple field `index`
  ambiguity, an implicit plotting type and immutable/loop defaults. Explicit
  table boundaries and types fixed them without relaxing strict checks.
- Early new burst tests demanded sample-exact abrupt Hilbert boundaries and
  identical masks after amplitude reduction. Those assumptions are invalid;
  cycle-scale timing/count/overlap tests replaced them while analytical power
  assertions remained tight. A fixture also counted only half its four outcomes;
  its expected grouping count was corrected.
- Unit-scale validation found an absolute sign-flip tie tolerance unsuitable for
  very small powers. A scale-relative tolerance now preserves p-values at
  scales 10^−20, 1 and 10^20, guarded by regression tests.
- The first sensitivity CLI invocation revealed a positional Typer config;
  it is now the requested required `--config` option and the full sweep ran.
- A Pandas warning from concatenating empty burst tables was fixed by retaining
  the schema but concatenating only nonempty run tables. Zero-detection records
  remain present in exposure/features tables.
- Figure review improved actual integer subject/run ticks and dark-cell label
  contrast. A configuration-generation helper without explicit plotting-cache
  environment emitted font-cache warnings; all verification workflows use
  designated writable caches. No scientific data were changed by figure fixes.

Only the initial five subjects and one local Python/platform environment were
verified. Population inference, long-burst survival modeling, a calibrated
small-n uncertainty method, measured electrodes, robust artifact diagnosis,
source localization, MRI, ML and cluster permutation analysis remain outside
this milestone. Cache reuse is conservative; it caches exact run outputs rather
than implementing speculative layered optimization. Percentile coverage is poor
at five subjects, reference choice changes conclusions, and detector definitions
change occupancy. These are findings to retain, not failures to hide by selecting
another configuration. Milestone 4 was not started.

# Milestone 4 verification — v0.4.0

The preceding sections are the preserved Milestone 3 historical record.
All 205 baseline tests were first verified unchanged (202 offline, 3 cached-data
integration). No baseline test file was edited for Milestone 4.

New verification covers tabulated t limits, basic reflection, translation/scaling
metamorphisms, missing/empty/degenerate groups, reproducible bootstrap streams,
unreliable studentized pivots, robust location targets, every generative scenario,
known normal and heavy/MNAR targets, perfect within-subject correlation, unequal
counts, independent-subject grouping, analytical reference variance/PSD identities,
minimum-run/trial eligibility, per-channel robustness flags, and explicit expansion.
Serial/two-worker chunk CSVs are byte-identical; resume does not duplicate chunks,
and altered parameters/corrupted checksums reject reuse. A simulated keyboard
interrupt preserves a completed recording and resumes the remaining three;
corrupt recording artifacts become explicit failures. Cached real subject 6
runs 4/8 confirm the new engine and resume without network access.

The full main simulation ran: 84,000 independent datasets, 420,000 intervals,
210 scenario/N/method summaries, 3,360 completed chunks. Coverage uncertainty
uses exact binomial 95% limits plus MCSE. See `MILESTONE4_RESULTS.md` for actual
coverage, targets, timings and scientific limits. CI uses only the small smoke
configuration. New CLI workflows were exercised on actual outputs.

The sealed 30-subject replication completed 90/90 recordings, retaining all 30
subjects and 1,258/1,350 imagery proposals. Initial-subject reference audit
completed 15/15. Figures were generated from saved tables; initial/replication,
forest, heatmap, QC, weighting, influence, calibration, correlation and artifact
examples were visually inspected. Rendering at font size 8 fits full replication
axis descriptions. Failed development audit directories are preserved separately;
the successful main audit is unambiguous. No result was inferred from a failed run.

Static verification: Ruff check, Ruff formatting, strict mypy (50 source files)
and installed-dependency compatibility checks pass. Only Python 3.12.2/macOS
ARM64 was executed locally; the CI matrix declares Python 3.11 and 3.12 but
remote CI execution is not claimed. Source/raw hashes and manifests retain the
actual software environment. Original EDFs and prior milestone outputs were
preserved. No GitHub push or Milestone 5 work was performed.

Final edge-case verification found and corrected empty-cohort Pandas object
columns before influence aggregation. The completed 30-subject results were
unaffected. Numeric empty columns and explicit empty influence-table schemas
now preserve a machine-readable all-failed result. Regression tests also reject
empty covariance inputs and non-imagery reference-audit runs. Missing
configuration estimates count against sign agreement and trigger an explicit
incomplete-evidence flag. These corrections do not change the frozen primary
analysis or its successful numerical backend.

The complete suite has **255 tests: 251 offline plus 4 cached-data integration**,
including all 205 baseline tests unchanged and 50 new tests. The exact source
used for the completed development sensitivity sweep is archived locally in
`reports/m4-execution-source/source.zip` with a checksum and software digest;
this makes its dirty-tree provenance recoverable. Final clean-commit replication
and audit reports are separately generated, preserving development generations.
