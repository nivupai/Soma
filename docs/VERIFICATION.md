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

The complete suite has **256 tests: 252 offline plus 4 cached-data integration**,
including all 205 baseline tests unchanged and 51 new tests. The exact source
used for the completed development sensitivity sweep is archived locally in
`reports/m4-execution-source/source.zip` with a checksum and software digest;
this makes its dirty-tree provenance recoverable. Final clean-commit replication
and audit reports are separately generated, preserving development generations.

A final missing-outcome audit added an independent exact-sign-pattern regression:
when only one primary channel is available, Holm still retains the planned
family of two (the unavailable comparison is conservatively p=1 internally).
Both primary channels were available in the completed cohort, so this follow-up
correction leaves all reported estimates and adjusted p-values unchanged. Main
clean scientific reports identify feature commit `3ac9715`; the correction and
its extra test are recorded in a subsequent local fix commit.

# Milestone 5 verification — v0.5.0

All **256 baseline tests passed unchanged before implementation**. The final
implementation passes **312 tests** including unit, numerical, adversarial and
cached-data integration cases (56 new). Exact original test file bytes are
compared with `e7624c0`. Ruff, Ruff formatting, strict mypy (65 source files),
dependency compatibility and CLI checks pass. `configs/decoding-verification.json`
records current software identity, command return codes and log hashes; the
logs are under `reports/m5-verification`.

New tests independently check analytic covariance, OAS/shrinkage scale/permutation,
SPD rank/floor/zero-energy behavior, diagonal and congruence Riemannian properties,
Euclidean versus geometric means, training tangent references, CSP known source
directions/order/rank, deterministic oscillatory mixtures, unequal class counts,
independent-label chance behavior and clear separated-class performance averaged
across independent simulations. The cache/raw-tensor prediction paths agree.
Cached real EEG confirms ordered 9×320 analysis and 9×640 context tensors,
consistent warm-cache fingerprints and explicit cache-identity corruption failure.

Adversarial tests reject global-fitted CSP/tangent/scalers, overlapping trials,
missing provenance, subject/run overlap, outer-test hyperparameter selection and
adaptation labels from evaluation runs. Changing outer labels cannot change
inner choices; extreme test input cannot change training scalers or thresholds.
A confounded fingerprint fixture gives 100% under trial-random splitting versus
50% on unseen subjects. Held-out tests use synthetic fixtures and temporary
paths only: stale code or an unfinished freeze fails before fetch/read, invalid
frozen choices fail, and a failed secondary held-out mode propagates partial status.
No real prospective data were read by verification tests.

The final development run completed 105/105 recordings, 1,441 retained trials,
105 within-subject partitions, five nested subject-disjoint outer folds, fixed
adaptation and all 19 complete nested permutation refits. All primary model/fold
cells succeeded. The supplementary post-hoc common-trial preprocessing diagnostic
preserves its 12 failed within-subject cells (S22 missing run 4 after intersection).
Primary preprocessing and prospective rules were not changed by that diagnostic.

All requested scientific figure types were generated and representative outputs
visually inspected. Saved caption documents specify subject Ns and uncertainty;
no source-localization maps or independent-trial intervals were introduced.
Known-mixture recovery and computational stages were measured on actual runs.
The final code development summaries are identical to the preserved initial run;
data-boundary/status refinements did not change the numerical model definitions.
Prospective results are recorded below after the separate committed freeze.


## Prospective Milestone 5 verification

The feature was committed as `3816e4e`; frozen development-only settings were
committed as `a6b458f` before any real access to subjects 36–65. Frozen checksum:
`7eced826d6024e633400917fb9dc1c2db26898b85b9ef6b6da47e67603f5d439`.
The source digest remains `8b737ed92e21614a9b013671` before and after evaluation.
All three prospective manifests identify clean freeze commit `a6b458f`.

All 90 requested target EDFs completed; 1,234 retained trials, 30 subjects,
all classes/runs present. All 999 pipeline fits completed: nine zero-shot,
180 fixed adaptation, 810 within-target run-held-out. A post-evaluation audit
rechecked the immutable frozen files against Git, chronological receipts, all
195 original EDF hashes, exact source/target groups, unique predictions,
absence of prospective inner tuning, balanced run-4 adaptation counts and
separate test runs. All 11 checks passed. Numerical/data/model choices were
not changed after held-out access. Audit code and hashes are retained with reports.

The released-code synthetic and benchmark workflows also completed. Synthetic
source-separated and independent-label results match the earlier validated
experiments; the benchmark records wall/CPU/allocation/RSS measurements for each
stage. Prospective and development figure captions specify subject N and CI
meaning, and representative high-resolution figures were visually inspected.

This adds real-data evaluation evidence, not extra unit-test counts: **312 tests**
remain the validated suite, with all 256 original files byte-identical. Only
Python 3.12.2/macOS ARM64 was executed locally; configured remote CI is not claimed.
The statistical and physiological limitations in `DECODING_METHODS.md` and
`MILESTONE5_RESULTS.md` remain part of the findings.


## v0.6.0 source validation

The unchanged v0.5.0 baseline passed all 312 tests before edits. The source suite
adds analytical/numerical geometry, SVD, rank, covariance, whitening, orientation,
resolution, mesh-geodesic, phase-cancellation and CLI tests. Explicit integration
compares fresh and cached actual fsaverage BEM fields, detects cache corruption,
checks fixed/free MNE inverse kernels and covariance/projector boundaries, and
compares Soma lead fields with MNE's own noiseless simulation. MNE's simulator
removes input projections: the test first checks unreferenced fields and then
explicitly adds average reference. Fifty source tests supplement the baseline.

`pytest`, complete cached integration, Ruff lint/format, strict mypy, dependency
checks, all source CLI workflows, 280 cortical simulations, a fresh forward
benchmark and the subject-1 trial-power demonstration are recorded in
SOURCE_MODELING_VALIDATION.md. Ordinary CI remains offline, including the small
analytical-sphere conductivity control; template tests are integration marked.


## v0.7.0 MRI verification

The clean 8a5ca65 baseline passed all 362 tests unchanged before implementation.
The new MRI suite checks physical voxel maps, NIfTI-1/2 forms/units/scaling,
4D selection, file truncation, RAS/LPS and SimpleITK indexing, scalar dtype
preservation, affine/shear normals, one-pass resampling, analytic intensity/label
behavior, rigid/affine independent landmark recovery, moment initialization,
serialization with nonzero centers, Dice/Jaccard/components, marching-cubes
convergence, pathological topology, exact triangle contacts, nested containment,
source-frame/subject compatibility and CLI behavior. Cached real integration
verifies SPM anatomy and the existing fsaverage lead field without fetching.
MRI_VALIDATION.md records executed checks and actual counts, including failures
that remain scientific results rather than hidden repairs.

## Milestone 8 — participant anatomy (v0.8.0)

Verified 2026-11-07 on macOS ARM64, Python 3.12.2. Before implementation the
unchanged v0.7.0 baseline passed all 421 tests (46.41 s). Final acceptance:
`pytest -o addopts='' -q` passed **461 tests in 48.47 s**, including 40 added
geometry, numerical, adversarial, CLI and integration tests and all 12 opt-in
integration cases. All 33 existing test files are byte-identical to the baseline.
There were 56 existing dependency/API deprecation warnings; no failures.
Ruff and formatting passed (195 files), strict mypy passed (120 source files),
and `pip check` found no broken requirements. Python 3.11 was not rerun locally.

Executed all six workflows under `reports/milestone8-verified`: synthetic lab,
coregistration, surface validation, participant EEG forward/inverse, uncertainty
sweep, and separate MEG forward-only fallback. Actual EEG dimensions are 59×1,239,
rank 58; MEG is 305×3,717 free components for 1,239 sources. Computational surface
readiness is PASS; overall anatomical readiness is INDETERMINATE. Actual curated
boundaries are FLASH, disclosed by a post-development amendment without altering
the sealed original protocol. No measured MRI fiducial truth was invented.

Synthetic BEM/analytical discrepancies decrease from 30.36% to 18.66%. Correct-model
cortical simulation still has 28.315-mm peak error and −98.967% current bias;
conductivity alternatives change the forward 14.50–37.33%. These unfavorable
results are retained. The 48-trial real example uses audiovisual labels and
separates phase-locked from trialwise power. Independent fresh MNE forward and
direct inverse adapter comparisons pass; these are not anatomical validation.

Final wall time/process peak RSS: synthetic 2.83 s/199.6 MiB; coregistration
2.22 s/320.0 MiB; surface validation 1.91 s/250.6 MiB; individual EEG 3.07 s/540.8 MiB;
21-case sweep 25.76 s/701.3 MiB; MEG 6.29 s/422.1 MiB. Cache state and individual
stage times are recorded; these are representative local runs, not universal
benchmarks. The explicitly fetched primary cache is approximately 2.7 GiB.

Twenty figures were visually inspected. All 92 manifest-listed outputs passed
SHA256 verification and 137 NPZ arrays loaded without pickle/object arrays or
nonfinite numeric values. Figure data companions were checked. Each manifest
matches the final Python source-tree SHA256. Runs precede the release commit and
record the then-dirty baseline revision; the exact tree hash binds their code.
The compact [verification receipt](../experiments/milestone8/verification.json)
preserves parameters, asset hashes, versions, transforms, seeds, metrics and
manifest hashes. Large assets and reports are intentionally ignored by Git.

Milestone 6 integration and Milestone 7 SPM-foreground rejection passed unchanged.
FreeSurfer watershed generation and ds000117 participant reconstruction were not
executed; secondary metadata discovery was. No Milestone 9 or remote push.
See [scientific validation and limitations](INDIVIDUAL_SOURCE_VALIDATION.md).

## Milestone 9 — model reliability (v0.9.0)

Baseline e7cf639 passed all 461 tests in 48.06 s before implementation. Final
`pytest -o addopts='' -q` passed **495 tests in 47.05 s**, including 34 added
geometry, calibration, unit, adversarial, CLI and opt-in MNE tests (13 integration
cases total). All 36 existing test files are byte-identical to the baseline.
The 56 dependency deprecation warnings remain; no tests failed. Ruff and formatting
passed (212 files), strict mypy passed (127 source files), and dependency checking
found no broken requirements. Installed and source versions both equal 0.9.0.
Python 3.12.2/macOS ARM64 were executed; Python 3.11/remote CI were not rerun.

The unchanged M8 coregistration and 21-case uncertainty commands were executed
before new numerical behavior; every historical case metric reproduced exactly.
All 98 original M8 report files remain byte-identical. The historical true-vertex
RMS current bias is valid in A m; resolution diagonal 0.0102446256 explains its
noise-free attenuation. Direct MNE agrees with the extracted kernel, and independent
small-matrix oracles verify Tikhonov gains/variance/regularization and interactions.

All five new commands completed under `reports/milestone9-validated`. The inverse
audit has 90 settings/270 source rows, selected resolution has 30/90, registration
has 800 base scenario attempts plus 100 explicitly separate robust fits, and paired
attribution has 680 source evaluations. The 100 rejected correspondence controls
are intentional; inverse/factorial experiments have no numerical failures.
Anatomical evidence remains INDETERMINATE, with same-pipeline derivative
discrepancies and unsupported independent truth documented. MNE nearest-vertex
`mindist` semantics explain the separately flagged submillimetre triangle clearance;
no source model, transform or old result was silently changed.

Representative final wall time / peak process RSS (cache state and CPU stages in
receipts):

| Workflow | Wall time | Peak RSS |
| --- | ---: | ---: |
| coreg | 5.03 s | 492.0 MiB |
| inverse | 5.49 s | 419.2 MiB |
| resolution | 3.73 s | 425.7 MiB |
| evidence | 8.93 s | 435.2 MiB |
| uncertainty | 3.81 s | 771.8 MiB |

Peak memory is process high-water including libraries, not incremental allocation.
No full dense cortical resolution matrix is allocated. Eighteen scientific figures
were visually inspected; all 58 listed output hashes and 208 NPZ arrays were checked
without pickle/object arrays or nonfinite numeric values. Every final manifest
records 0.9.0 and the same exact final Python source-tree hash. A stale editable
metadata installation was detected during artifact checks, corrected, regression
checked and all five reports rerun into the new validated directory; earlier report
attempts were not relabeled.

See the [verification receipt](../experiments/milestone9/verification.json),
[frozen protocol](MODEL_RELIABILITY_PROTOCOL.md) and
[scientific findings](MILESTONE9_RESULTS.md). The full suite includes unchanged
M6–8 source/geometry/integration regressions. No independent anatomical/clinical
certification, population guarantee, remote push or Milestone 10 implementation.
