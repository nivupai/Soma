# Multi-subject research protocol: Milestone 3

This is a predefined exploratory replication and robustness protocol. No
configuration is selected after seeing results and treated as confirmatory.

## Cohort, selection and statistical units

The primary validation cohort is PhysioNet EEGBCI subjects 1–5, unilateral hand
imagery runs 4, 8, 12: 15 independently processed EDFs. An expanded 1–10 cohort
can be specified in YAML but was not requested for download here. Analysis reads
only explicitly selected cached recordings. Download is a separate action using
the existing adapter. No external subject exclusion list is applied.

Every table retains subject, run and recording identity; event/trial tables
retain annotation identity, seconds and samples. Recordings are not concatenated.
The adapter validates 64 EEG channels at 160 Hz. The cohort engine additionally
compares full EEG channel sets and sampling rates across successful run artifacts.
Missing files, unreadable/incomplete EDFs, missing/overlapping annotations,
unmatched channels, unexpected sampling, nonfinite data and insufficient filter
support are recorded per file, not silently repaired. A failed record does not
discard other successful records. No run or subject is inferred from file order.

The independent population unit is the subject. A missing condition makes that
run's paired contrast unavailable. A subject with no valid paired run is missing
for that outcome. Remaining paired run contrasts receive equal weight within
subject; subject means receive equal weight in the cohort. Trial counts affect
precision but never population sample size. Partial-cohort results describe the
available subjects; missingness need not be random.

## Primary and exploratory outcomes

Primary: C3 and C4 mu-band left-minus-right **mean log absolute trial power**,
paired within run then averaged within subject. Positive means higher left-hand
imagery power at that sensor, not higher activation. C3/C4 are anatomical labels;
the contralateral interpretation is a sensor convention, not source evidence.

Exploratory: beta, Cz, arithmetic absolute-power differences, ERD percentage-point
and normalized log contrasts, run SDs, C3/C4 lateralization, burst occupancy,
onset rate, complete duration, amplitude, and burst–power associations. Retain
absolute values regardless of reference availability. Means of log trial powers,
logs of mean powers and mean percentage changes are different estimands.

C3/C4 contra-minus-ipsi conventions:

- Left hand: C4 minus C3; negative means lower C4 power.
- Right hand: C3 minus C4; negative means lower C3 power.
- Condition-by-sensor interaction: (left C4−C3)−(right C4−C3); negative means
  a more negative left C4−C3 difference together with a more positive right one.
- Right C4 minus left C3 is a separate sensor/condition comparison, not the same
  interaction. Log variants use explicit ratios of arithmetic condition means.

## Primary processing and QC

Defaults retain Milestone 2: average of all available validated EEG channels,
continuous 1–40 Hz Butterworth prototype order 4, forward-backward SOS filtering,
no notch, no ICA, no resampling. Exact coefficients, effective gain/phase,
frequency-response crossings and operational transient guards are saved for every
run. Analysis is annotation-contained [1,3) s; Morlet context [0,4) s. Standard
1005 head-frame positions in meters remain explicitly template geometry.

Operational channel peak-to-peak ceiling is 500 µV; trial ceiling 300 µV; absolute
excursion 150 µV; flat SD below 0.05 µV. Channel flags do not automatically remove
sensors from average reference. Trial thresholds apply to selected C3/Cz/C4;
every rejected proposal is logged. High amplitude is a flag, not a confirmed
artifact diagnosis. Boundary guards are independent of amplitude criteria.

The default power reference is separately accepted T0 rest in each run. Matched
[−3,−1) s references must be fully inside actual rest and pass duration, QC and
boundary checks. No reference is invented, copied across runs or replaced by
epsilon. Absolute power stays available when normalized quantities are missing.

## Predefined sensitivity design

`configs/sensitivity.yaml` specifies a ten-configuration one-factor-at-a-time
sweep. Each comparison changes one policy/factor relative to primary:

| Variant | Change and reason |
| --- | --- |
| primary | Average, 1–40 Hz, condition rest, operational QC |
| reference_none | Acquisition reference retained; tests spatial reference dependence |
| reference_fz_pz | Arithmetic Fz/Pz reference; valid alternative, not presumed neutral |
| filter_05_40 | Only high-pass becomes 0.5 Hz; tests drift/boundary sensitivity |
| filter_1_45 | Only low-pass becomes 45 Hz; tests upper-band filtering |
| normalization_none | Absolute values retained; normalized outcomes unavailable |
| normalization_matched | Actual matched rest instead of pooled rest |
| qc_strict | Amplitude ceilings ×0.5; flat threshold unchanged |
| qc_permissive | Amplitude ceilings ×1.5; flat threshold unchanged |
| burst_high_25 | Dual high threshold 2.5× accepted-rest median instead of 2× |

No Cartesian product is generated. The fixed reference comparator requires Fz
and Pz; a missing reference channel fails that run explicitly. Every variant
retains effects, subject/run/trial counts, reference missingness, and burst
threshold outcomes. Differences in effective subject sets are visible. Matched-
subject changes and sign consistency are reported alongside changes in aggregate
means. Relative changes divide by |primary| only if nonzero; ratios near zero
are unstable, so absolute effect changes and retention are the first summaries.
Power normalization alone should not change absolute-power results when the
same trial sets remain. Threshold changes should not change spectral results.

## Burst protocol

Detection is continuous, separately for each selected channel/run and mu [8,13]
or beta [13,30] Hz. NeuroDSP applies a seven-cycle FIR and Hilbert amplitude.
Reflect padding, FIR support and an extra two-second Hilbert guard are explicit;
the broad-band preprocessing guard is added. Hilbert support is mathematically
nonlocal: these guards are operational, not a proof of no edge influence.

Two primary, channel-specific rest-calibrated strategies are always compared:

1. `rest_dual`: low=1× and high=2× median amplitude on accepted valid T0 samples.
2. `rest_percentile`: low=75th and high=95th percentile of the same amplitude.

A fixed-voltage strategy is available for synthetic calibration, not silently
applied to real EEG. Detector thresholds concern amplitude in volts, not power.
The NeuroDSP wrapper rescales to its internal whole-input median normalization,
so the final physical thresholds are the documented rest/fixed amplitudes.
Minimum continuous duration is three cycles at the lower band edge.

Report valid exposure, occupied time, occupancy, onset count/rate, amplitude and
complete-duration sums/counts. Window-clipped or guard/gap-clipped fragments are
censored. They contribute observed occupancy/amplitude but not complete-duration
means. Their entrance into a window is not counted as a new onset. Rates divide
by actual valid exposure, not nominal trial count. Zero bursts with exposure is
zero occupancy/rate; absent rest calibration or exposure is unavailable. Event-
relative 100 ms occupancy bins retain exposure and counts, not independent-event
claims. Complete-duration histograms are pooled descriptions, not population tests.

Within each run/condition, occupancy and rate use summed exposure/numerators;
amplitude uses summed burst samples; duration uses complete bursts. For subject
contrasts, paired run summaries receive equal run weight. Burst–power correlations
use subject-level paired contrasts and report pairwise effective n. They describe
association and cannot explain the causal mechanism of power suppression.

## Uncertainty and optional tests

For every channel/band/outcome, draw subjects with replacement at the outer level
and average their paired contrasts. Default: seed 42, 2,000 draws, pointwise
nominal 95% percentile intervals. No trial-level shuffling or bootstrap occurs.
Fewer than two available subjects gives no interval. Subject SD, paired-run n,
effective subject n and leave-one-subject-out estimates remain available.
Standardized mean contrast divides the cohort contrast by its subject SD and is
unavailable for zero SD; it is descriptive paired d_z, not a bias-corrected effect.

These are **nominal** intervals. In the recorded independent normal-subject
Monte Carlo experiment (200 replications), coverage was 93.5% at n=40 but only
80.5% at n=5. The small-cohort intervals must not be treated as calibrated 95%
evidence. Coverage depends on distribution, n and estimator; this diagnostic
is not a general correction or guarantee. It is distinct from one seeded
regression test. The results include binomial uncertainty on estimated coverage.

Optional two-sided sign flips act on independent subject contrasts and require
a symmetric null contrast distribution. Up to 16 subjects, enumerate all 2^S
patterns; beyond that use seeded Monte Carlo with a plus-one correction. A
scale-relative floating-point comparison preserves voltage-unit invariance.
With five subjects even perfect sign agreement has minimum two-sided exact
p=2/32=0.0625. Holm correction covers the entire power channel×band×outcome family
tested in that execution; no uncorrected multiple-location inference is made.
Burst and lateralization CIs remain descriptive. Sign flips are disabled in the
primary five-subject cohort. No cluster permutation method is implemented.

## Interpretation boundaries

The validation cohort is small, recordings and trials can be dependent, templates
are not measured anatomy, thresholds are operational, and filtering/referencing
can change the observed effects. Comparisons across variants must retain all
configurations and their missingness; no best-looking setting is promoted.
Replication means characterizing consistency and variation, not asserting that
every subject has the expected physiology. No decoding, clinical claim, MRI,
source localization or Milestone 4 work is included.

A reference or filter change can alter which trials pass the same QC thresholds.
Observed sensitivity differences therefore include induced selection effects;
they are not isolated effects of a signal transform on an identical trial set.
Matched-subject comparisons control subject membership, not all trial membership.
