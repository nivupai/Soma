# Milestone 4 prespecified replication protocol

Frozen before reading new-cohort results, using only Milestone 3 commit d92a93b.
The machine-readable definition is configs/replication.yaml; its canonical full
SHA-256 is in configs/replication.sha256. Its creation receipt records the source
commit, timestamp and document/config hashes. Changes to a frozen definition
require a new protocol identity and output directory, not a silent primary change.

Primary question: do sensor-level hand-imagery mu contrasts observed in the
initial five participants replicate in a distinct 30-participant sample? Subjects
6–35, runs 4/8/12, are the initial replication cohort. Subjects 1–5 are the
previously inspected development cohort. Hypotheses informed by those data are
exploratory, even though the new sample is distinct. All-subject expansion
requires an explicit selection option; nothing downloads all 109 automatically.

Primary outcomes: C3 and C4 mu (8–13 Hz) left-minus-right mean log absolute trial
power, paired within run, equal paired-run average within subject, then equal
subject mean. Positive means greater left-imagery sensor power. Beta, Cz,
normalized powers, lateralization, bursts and robust location summaries are
secondary/exploratory. Trial-weighted and pooled-run estimates are separately
labeled different estimands. More surviving trials never increase a participant's
primary population weight.

Primary processing remains continuous 1–40 Hz order-4 prototype Butterworth SOS,
zero phase, average reference over validated EEG, no notch/ICA/resampling,
C3/Cz/C4 analysis, annotation-contained [1,3) s PSD windows, [0,4) s Morlet context,
accepted same-run T0 reference, existing operational QC and transient guards.
Use original EDFs and per-run boundaries. Read actual sampling/channel metadata;
unexpected rates or mismatched sets are recorded and rejected, not silently
resampled. Template coordinates remain template, never measured anatomy.

Include a run if the existing loader, event, geometry and signal validation pass.
A paired run needs at least one retained trial per hand. A primary subject needs
at least two paired runs for that outcome. Missing records and failed runs remain
in coverage; subjects below the rule receive an explicit exclusion reason.
No external exclusion list or post-result physiological exclusion is permitted.
Missing reference values are unavailable; absolute power is retained. Complete-
case inference assumes the retained subjects represent the target cohort;
nonrandom missingness is assessed in a designated simulation, not assumed away.

Primary uncertainty uses a nominal two-sided 95% Student t interval on independent
subject means, selected before new results because the replication sample is
larger and the mean has an analytic subject-level standard error. Normality or
adequate CLT behavior is an assumption, not a promised property. Percentile,
basic, studentized and BCa intervals are also reported. No method replaces a
failed method or becomes primary because its interval looks favorable. BCa is
not presumed to cure small-sample undercoverage. Robust median and 20% trimmed
means are different location targets, not bias-corrected versions of the mean.

Optional paired subject sign flips require independent symmetric null contrasts.
Holm correction covers the two primary C3/C4 mu tests. Other intervals are
pointwise exploratory descriptions; no uncorrected secondary multiple-location
significance claim is made. No mixed-effects model or trial-level randomization
is introduced without a separately specified model and diagnostics.

Sensitivity uses the ten fixed Milestone 3 one-factor-at-a-time variants.
Reference/filter changes can change QC retention; both common-trial and retained-
trial comparisons must be distinguished in the reference audit. Quantify
reference transforms, covariance/common mode, spectral cross terms and influential
subjects/runs/trials. No physically impossible reference invariance is required.

Operational robustness criteria are declared in the YAML: at least 80% subject
and record coverage, at least 70% imagery retention, at least 95% leave-one-subject
sign agreement, at least 80% configuration sign agreement, and at most 10%
unavailable normalized reference cells for a referenced analysis. Flag a sign
flip across references explicitly. A failed criterion marks instability or
insufficient evidence, not proof that physiology is absent or a license to select
another configuration. Subject sign fractions are descriptive, not an inclusion
criterion. Calibration failures/missingness also produce explicit warnings.

Calibration compares five interval methods at N=5,10,20,30,50,100, 2,000 independent
replications per main scenario/sample-size cell, 1,999 bootstrap draws per dataset.
Scenarios cover a normal benchmark, correlated/unequal repeated measures,
heteroscedasticity, finite-variance heavy tails, contamination, designated nonrandom
missingness and a preprocessing shift. Data-generating structural truth and each
estimator's observed-data target are recorded separately. Bias, variance, RMSE,
coverage, width, failures and Monte Carlo uncertainty are saved. Deterministic
SeedSequence streams depend on scenario, N and replication identity, not worker
or task scheduling. Smaller smoke configurations serve CI only.

This protocol is fixed before new subject analyses. The verification record may
later document execution and deviations, but no primary rule is rewritten after
viewing replication results. No classification, MRI/source reconstruction or
Milestone 5 work is authorized here.
