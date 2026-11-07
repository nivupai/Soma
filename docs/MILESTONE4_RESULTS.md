# Milestone 4 execution and scientific results

Soma v0.4.0. Protocol frozen at 2026-11-07 03:40:19 UTC, before new-cohort
fetch/analysis. Canonical protocol SHA-256:
`9995060c58ffb3a896d725ef9641f27fb7645950b76fbbf59b6ee97f3488ab61`.
The primary configuration and t interval were not changed after results.

## Dataset coverage and estimands

All 90 requested EDFs for subjects 6–35 × runs 4/8/12 downloaded and completed.
All 30 subjects had three paired runs and met the minimum-two-run criterion.
No recording or subject was excluded; 1,258/1,350 imagery proposals survived QC
(93.185%). Every analyzed record reported 160 Hz and compatible EEG channel sets;
no resampling occurred. No missing primary condition-rest references occurred.
The original five-subject reference audit completed 15/15 recordings.
EDF hashes, event proposals, accepted/rejected trial identities, thresholds,
geometry and warnings remain in the output artifacts. No outside exclusion list
was applied. No subjects outside the requested 6–35 cohort were downloaded.

These are left-minus-right mean log-power contrasts with equal run weights
within subject and equal subject weights in the population. Intervals below are
pointwise nominal 95% subject t intervals, not simultaneous confidence bands.
The initial estimates are re-expressed with the same interval procedures for a
fair comparison; original M3 outputs remain intact. Hypotheses informed by those
five subjects remain exploratory despite the disjoint replication cohort.

| Cohort | Channel | Band | N | Estimate | 95% t interval |
|---|---|---|---:|---:|---|
| initial_1_to_5 | C3 | beta | 5 | 0.054245 | [-0.139558, 0.248048] |
| initial_1_to_5 | C3 | mu | 5 | 0.134851 | [-0.200085, 0.469786] |
| initial_1_to_5 | C4 | beta | 5 | -0.045273 | [-0.154025, 0.063478] |
| initial_1_to_5 | C4 | mu | 5 | -0.187216 | [-0.251844, -0.122588] |
| replication | C3 | beta | 30 | 0.071527 | [0.016113, 0.126940] |
| replication | C3 | mu | 30 | 0.080111 | [-0.032066, 0.192288] |
| replication | C4 | beta | 30 | -0.113985 | [-0.178685, -0.049285] |
| replication | C4 | mu | 30 | -0.242587 | [-0.363338, -0.121836] |

C4 mu retains the negative sensor contrast. C3 mu remains uncertain. Beta
contrasts are exploratory secondary findings. Sensor power depends on reference
and does not identify a localized neural generator or establish causality.

## Statistical calibration

Seven scenarios × six sample sizes × 2,000 independent datasets = **84,000 datasets**,
with five methods and 1,999 bootstrap resamples each: **420,000 intervals**,
210 summary cells. This is the completed main grid, not a smoke extrapolation.
The normal benchmark illustrates why five-subject empirical bootstrap intervals
undercover. Even BCa remains poorly calibrated at N=5. Failure rates below apply
to this normal benchmark; stress-test failures are retained in the full CSV.

| N | Method | Coverage | Exact 95% Monte Carlo interval | MCSE | Mean width | Failure |
|---:|---|---:|---|---:|---:|---:|
| 5 | basic | 83.85% | 82.16–85.44% | 0.82 pp | 0.574 | 0.0% |
| 5 | bca | 83.15% | 81.44–84.77% | 0.84 pp | 0.595 | 0.0% |
| 5 | percentile | 83.30% | 81.59–84.91% | 0.83 pp | 0.574 | 0.0% |
| 5 | studentized | 94.25% | 93.14–95.23% | 0.52 pp | 1.429 | 0.0% |
| 5 | t | 94.45% | 93.35–95.41% | 0.51 pp | 0.926 | 0.0% |
| 30 | basic | 93.15% | 91.95–94.22% | 0.56 pp | 0.279 | 0.0% |
| 30 | bca | 93.25% | 92.06–94.31% | 0.56 pp | 0.280 | 0.0% |
| 30 | percentile | 93.30% | 92.11–94.36% | 0.56 pp | 0.279 | 0.0% |
| 30 | studentized | 94.65% | 93.57–95.60% | 0.50 pp | 0.298 | 0.0% |
| 30 | t | 94.65% | 93.57–95.60% | 0.50 pp | 0.297 | 0.0% |

At N=30, t coverage across the seven observed-data targets ranged from 92.8%
(contamination; MCSE 0.58 percentage points) to 95.35% (MNAR selected target;
MCSE 0.47 pp). BCa contamination coverage was 89.65% (MCSE 0.68 pp).
The MNAR t interval covered the selected target 95.35% but the original structural
effect only 70.75%. Preprocessing-shift structural coverage was 73.75% for t.
Good sampling calibration around a biased target cannot recover the clean
scientific effect. These results support no universally superior procedure;
heavy tails, contamination, missingness and finite bootstrap support all matter.
Full bias/variance/RMSE/width/failure/warning and binomial-limit data are saved.

## Why the original C3 reference sign changes

Across subjects 1–5, C3 mu equal-subject log contrasts were +0.134851 with
average reference, −0.102075 with acquisition reference retained (`none`), and
+0.029485 with Fz/Pz. `none` is not an absolute physical voltage reference.
The average→none change was −0.236925. On the identical accepted-trial
intersection the transform change was −0.233797, leaving −0.003129 as the
trial-selection accounting remainder. Thus most of this observed sign reversal
persists without changing trial membership. Fz/Pz's total change was −0.105366,
shared-trial transform change −0.082918, remainder −0.022448.

C3 average→none subject changes were S1 −0.379599, S4 −0.331751,
S3 −0.294336, S2 −0.171347 and S5 −0.007593. The largest common-mode principal
component accounted for 44.3–84.0% of filtered acquisition-reference channel
variance across audited runs. This supports substantial shared variance; it is
not proof that the shared component is an artifact. Reference subtraction changes
power through both reference power and channel-reference cross spectra.
Maximum variance-identity residual was 1.14e−24 V²; maximum integrated spectral
identity residual was 3.68e−25 V². Numerical reference algebra is therefore
consistent; sensor power has no physical requirement to be reference invariant.

Trial diagnostics include S2/R12 C3 mu average-reference right-imagery proposal
9: deleting it changes that **run** contrast by −0.259928. S1/R12 proposal 1
under acquisition reference changes it by −0.254491. These are trial/run
contributions, not independent population observations. Saved excerpts select the
largest peak-to-peak proposal per run for visual review. They show shared signal
and reference changes, without validating an ocular/muscle artifact diagnosis.
Template positions remain explicitly unmeasured.

## Influence and weighting

All 30 single-subject deletions preserve the primary C3/C4 mu mean signs.
Largest absolute C3 change: removing S33, +0.080111→+0.037580 (−0.042531).
Largest C4 change: removing S34, −0.242587→−0.209059 (+0.033528).
C3 median/20%-trimmed location: +0.028359/+0.048507;
C4: −0.181902/−0.202133. These target different locations under asymmetry.
Positive-subject fractions were 19/30 C3 and 8/30 C4, descriptive only.
Trial-weighted mu estimates were +0.077212 C3 and −0.246458 C4; equal run
and equal subject estimates coincide because all subjects retained three runs.
Run deletion and subject influence tables retain the declared eligibility rules.

## Measured performance

Initial sequential 90-record replication: 88.54 seconds wall time; no warm cache
hits. Run profiles show peak process high-water RSS 444.80 MiB and maximum
traced run allocation 49.56 MiB. Summed preprocessing 16.04 s, TFR 11.24 s,
burst detection 38.68 s; stages can overlap in included totals and do not add
exactly to wall time. Only one raw recording is processed at a time.
Main calibration: 50.52 s wall, four workers on macOS 15.7 ARM64, ten logical
CPUs; parent peak RSS 135.77 MiB, maximum child RSS 127.05 MiB. Child high-water
RSS is not the simultaneous sum across workers. 3,360 chunks completed.
These are actual local measurements and are not portable performance guarantees.
Other verification/audit work could run concurrently; this is not an isolated
hardware throughput benchmark.

## Reproduction, figures and limitations

See README commands and `REPRODUCIBILITY.md`. Main outputs reside in
`reports/m4-replication-main`, `reports/m4-sensitivity-main`,
`reports/m4-calibration-main`, `reports/m4-reference-audit-main`.
Saved tables support forest, initial-vs-replication, subject/run heatmaps,
QC, weighting, influence, reference, coverage, width, failure and bias/RMSE figures.
Representative figures and artifact excerpts were visually inspected. Replication
figure rendering uses Matplotlib font size 8 to fit complete axis descriptions;
this changes rendering only. Nominal intervals do not certify physiology.

Missingness can bias the observed sample, automatic QC is not expert artifact
review, sequential IDs need not be random population sampling, and no demographic
or clinical generalization is established. The simulation models are stylized
log-power models with specified finite variances, not comprehensive EEG physics.
Sensitivity sign agreement is an operational warning rule, not proof of
invariance. No decoding, ICA, source reconstruction or MRI was implemented.
A proposed next milestone is a separately prespecified expanded replication with
reviewed artifact labels and explicit missingness/selection models. It has not
been started.

The exploratory symmetric-null sign-flip estimates were p=0.15165 for C3 mu
and p=0.00010 for C4 mu; the two-test Holm values were 0.15165 and 0.00020.
These Monte Carlo p-values use 19,999 sign draws and their declared symmetry
assumptions. They do not change the prespecified primary t intervals.

Studentization can fail under extremely small effective N: in the N=5 MNAR
scenario its failure rate was 48.5%, with unconditional coverage 49.1%.
Other procedures failed on 4.4% of those datasets with insufficient/degenerate
observed subjects. At requested N=10, the MNAR studentized failure rate was 1.0%.
Failures are counted rather than concealed by conditioning on successful fits.

Leave-one-run mu estimates stayed +0.072945 to +0.089397 for C3 and
−0.255398 to −0.227981 for C4. The largest absolute run-deletion changes were
0.009286 and 0.014607, respectively. Two runs remained after each deletion,
so primary run eligibility was preserved in this cohort.

## Full prespecified sensitivity sweep

All **900/900** recording/configuration analyses completed across the ten frozen
variants; none failed. Both primary mu mean signs agreed in 10/10 variants and
30/30 subject deletions, passing the declared descriptive criteria. This does
not establish reference invariance: C3's point estimate fell 86.8% under the
acquisition reference, and all C3 mu t intervals included zero.

| Variant | C3 mu estimate | C4 mu estimate |
|---|---:|---:|
| primary | 0.080111 | -0.242587 |
| reference_none | 0.010591 | -0.119633 |
| reference_fz_pz | 0.052689 | -0.186859 |
| filter_05_40 | 0.102862 | -0.221163 |
| filter_1_45 | 0.080871 | -0.242237 |
| normalization_none | 0.080111 | -0.242587 |
| normalization_matched | 0.080111 | -0.242587 |
| qc_strict | 0.083293 | -0.222992 |
| qc_permissive | 0.079653 | -0.242389 |
| burst_high_25 | 0.080111 | -0.242587 |

Strict QC retained 1,103/1,350 proposals (81.70%) and excluded S22 from the
primary subject summary because only one paired run remained (29 eligible
subjects). The primary configuration retains S22 and all 30 subjects. Per-variant
recording/subject coverage, retention and reference availability are saved.
Acquisition-reference retention was 86.52%; permissive QC retained 93.33%.
Matched-reference normalization had 7.63% unavailable normalized reference cells;
primary condition-rest normalization had none. `normalization_none` deliberately
leaves normalized outcomes unavailable (100%); this is an absent estimand by
configuration, not 100% artifact failure. Normalization and burst-threshold
changes leave the absolute log-power estimand unchanged by construction; the ten
sign checks are correlated and are not ten independent replications.

The exact sweep source is archived at `reports/m4-execution-source/source.zip`.
After the empty-cohort edge fix, final committed-code sensitivity artifacts
recompute robustness and rendering from its checksummed saved tables, preserving
the original scientific provenance. Fresh replication, calibration and reference
audit outputs under `reports/milestone4-committed/` carry the final revision.

Post-feature-commit clean regeneration produced byte-identical replication
features, subject contrasts and population intervals; the calibration summary
and reference-accounting table were also byte-identical. The clean repeat took
103.02 s for replication and 64.00 s for calibration while those workflows ran
concurrently. Their manifests identify clean feature revision `3ac9715`.
A subsequent missing-outcome Holm correction retains the planned two-test family
if one primary outcome is unavailable; both were observed here, and recomputing
all inference confirms unchanged estimates, intervals and adjusted p-values.
