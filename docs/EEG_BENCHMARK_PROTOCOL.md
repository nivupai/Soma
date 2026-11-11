# EEG decoding benchmark v22: sealed evaluation plan

This is a local prospective execution seal, **not independent preregistration**.
The M19 seal in `configs/eeg-benchmark-v22.json` was created before this execution's
human classification outcomes. It binds the exact private 195-file inventory,
scientific design, models, sensitivities and interpretation policy. The private
inventory records scoped participant keys and EDF hashes; only its fingerprint
is published. No new external evidence was provided: OSF registration, MRBrainS
authorization, ds000114 derivatives and audited task/session correspondence remain
NOT_AVAILABLE. No new download or fMRIPrep execution is authorized by this plan.

All 65 cached participants were used previously: M1–M3 examined the initial five;
M4 examined 6–35 (90 recordings), with an original-five reference audit; M5 developed
on 1–35 and evaluated 36–65. Those last 30 are no longer untouched. M20/M21 further
reused participants 1/2. Thus this study evaluates **held-out fitting on historically
reused EEGBCI**, not independent external replication. Method choices and the 8–30 Hz
sensitivity were informed by historical findings. No configuration is promoted
into the primary analysis after outcomes.

The frozen rule selects every cached participant in ascending source-number order:
first 35 source-role, remaining 30 evaluation-role. Imagery runs 4/8/12 only;
T1=left hand=0, T2=right hand=1 in that run context; T0 rest is excluded. Execution
runs and bilateral imagery are incompatible. Each participant needs all three
runs with at least two accepted trials per class/run. Record missing files, QC
rejections and failed model cells; never substitute or exclude by decoding score.
The raw recording headers and authoritative task context are verified by the
existing M20 EEG adapter. [PhysioNet EEGMMIDB](https://physionet.org/content/eegmmidb/1.0.0/)
describes the 160 Hz, 64-channel acquisition and run-specific annotations.

Primary: volts, 160 Hz, fixed fourth-order zero-phase 1–40 Hz filtering, average
reference across all EEG channels, nine FC3/FCz/FC4/C3/Cz/C4/CP3/CPz/CP4 motor channels,
epoch [1,3] s after cue, context [0,4] s. Existing QC: channel peak-to-peak 500 µV,
trial peak-to-peak 300 µV, excursion 150 µV, flat standard deviation 0.05 µV.
Fixed signal transforms operate per recording/trial, without label-dependent
learning. There is no target-population covariance normalization.

Within-subject: each target's run is held out, training on its other two runs.
Zero-shot: all source-role trials train the model; every target subject is disjoint.
Source-only three-fold grouped inner CV selects LR C in {0.1,1}, CSP components
{2,4} and regularization {0.1,0.3}. Inner objective averages subjects equally.
The selected parameters are fixed for target within-run and zero-shot evaluation.
Models are majority, log mu/beta band power LR, CSP LDA, Riemannian MDM and tangent
space LR. The existing estimators and scientific guards remain unchanged.

The primary endpoint equally averages run balanced accuracy within target, then
subjects. Report ordinary accuracy, recalls, pooled confusion counts, AUC and
supported probability metrics. Use 1,999 paired subject bootstrap resamples,
seed 22042; conditional on fitted source models. See the statistics and robustness
documents for limitations, fixed nulls and adaptation. All eleven configurations,
all inner candidates and failures remain auditable; no hidden model search.

## Execution implementation correction

The first execution stopped after source-only parameter selection while publishing
its FitAudit: the destination directory did not exist. No outer target model cells
were evaluated. A directory-creation correction was tested through a full fictional
eleven-variant execution, resumption and corruption rejection. The final execution
uses a separate output identity with the corrected source hash. The sealed scientific
protocol, inventory, QC, hyperparameter ranges and interpretation remain unchanged.
The aborted source-only receipts remain private and are not silently overwritten.

A second implementation correction was identified during inspection of the
no-reference sensitivity: minimum-class-count QC failures retained a failure row
but had not retained already-known proposal/accepted counts and per-trial decisions.
The corrected loader records those values before applying class-count eligibility,
and persists coverage even when no dataset can be assembled. A fictional transport
regression test covers the failure path. Earlier primary/sensitivity scores had
been inspected by this point; the scientific design was not amended or optimized.
All configurations are rerun under a new source identity, without reusing completed
variant receipts from the earlier implementation. Aggregate readers additionally
reject nested participant/trial payload fields. Earlier private outputs remain
separate. This is a reporting/privacy correction, not a new preregistration claim.
