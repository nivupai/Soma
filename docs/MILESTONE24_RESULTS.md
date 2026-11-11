# Milestone 24 results — new archived models, external evaluation blocked

Soma v0.24.0 trained and archived authentic new source-only EEG models. These are
not the missing original M22 fitted weights. No external human EEG was acquired
or evaluated. Historical M22/M23 scientific artifacts and tests remain unchanged.

## Actual release and coverage

Release ID: `8ce2e0952dce6f770a15ae70b99863d8712ec3017de951bba37bf3ef070afe85`.
Protocol: `1728ec7911c62612f4c4735267b5196d881d6e40ab069028c26ee0a9b5a83fcb`.
The local seal precedes this fit; it is not external preregistration. The protocol
was prospective for archiving state before future external evaluation, not an
untouched design: M22 source outcomes and parameter choices were already known.

| Quantity | Observed |
|---|---|
| Dataset | EEGBCI/eegmmidb v1.0.0, existing permitted local cache |
| Training role | Declared source subjects1–35 only |
| Recordings |105/105, runs4/8/12; input hashes match corresponding M22 records |
| Eligible participants |35/35; no participant substitutions |
| Retained trials |1,441; recording-level proposal/rejection decisions retained privately |
| Families archived | Majority, band-power LR, CSP LDA, Riemannian MDM, tangent LR |
| Archive/bank/source-CV wall time |4.98s on local macOS arm64/Python3.12; excludes EDF preprocessing and process startup |
| Newly acquired external signals |0 |
| External human subjects/sessions/trials |0/0/0 |

Complete state includes scaler means/scales, coefficients/intercepts, four CSP
filters, ordered SPD MDM class means and the tangent reference. Feature units,
order, class/tie semantics, hyperparameters, source fingerprints, M19 protocol,
code/dependency/backend identity and bounded M17 array hashes are bound to the
release. The capsule IDs and reviewed aggregate facts are machine-readable in
`experiments/milestone24/release-evidence.json`; private numerical arrays are not
published. Real coefficients, filters and covariance means can reveal cohort-derived
information. No privacy guarantee, differential privacy or redistribution clearance
is asserted merely because they are model parameters.

## Original versus independently reloaded outputs

All five models reproduced all1,441 original training-session labels exactly.
Decision scores also matched exactly: maximum absolute difference0 for every model.
All supported probability outputs matched exactly; MDM probabilities are unsupported.
The frozen fallback tolerances are rtol1e-9/atol1e-9, not retrospectively selected.

Two restarted processes from a different working directory used a fresh noneditable
Soma wheel and faithful training-dependency snapshot. Every estimator fit method was
disabled. No estimator object, training cache object, hidden global or executable
pickle was loaded. This verifies prediction-state reproduction with fixed probe
features, rather than independent end-to-end EDF preprocessing.

A separately resolved fresh environment was correctly BLOCKED: it installed nibabel
5.5.0 versus training5.4.2 and had different installation-record fingerprints. That
case is not relabeled portable. The successful isolated snapshot copies dependency
files together with their original metadata; it excludes Soma/services source,
editable hooks and training objects, then installs Soma noneditably. Existing exact
environment/source guards remain unchanged. See [reload verification](MODEL_RELOAD_VERIFICATION.md).

The initial fit completed once. A duplicate invocation refused to overwrite the
immutable release; it did not generate another set of fitted weights. Verification
uses the completed release, not an overwritten or retrospectively edited artifact.

## Descriptive source-cohort evaluation

Three fixed subject-grouped folds reuse the relevant M22 source-selection procedure
with its previously selected settings. No parameters are selected again. The final
release fits all source trials; fold metrics assess that fitting procedure, not the
final all-source weights on an independent cohort.

| Method | Mean BA | Median BA | Conditional95% interval | Left / right recall |
|---|---:|---:|---:|---:|
| Majority |50.00% |50.00% |50.00–50.00% |0.00 /100.00% |
| Band-power LR |60.50% |61.90% |56.54–64.68% |60.75 /60.24% |
| CSP LDA |55.21% |54.76% |52.81–57.95% |58.48 /51.93% |
| Riemannian MDM |51.77% |50.00% |50.07–54.08% |49.80 /53.74% |
| Tangent LR |57.04% |57.14% |54.71–59.52% |64.79 /49.30% |

All35 planned source participants contribute to each method; no validation
participant is missing. Participant distributions and trial membership remain
private; aggregate mean/median, recall, coverage and intervals are published.
Intervals resample participants1,999 times with seed24042. They are pointwise,
conditional on this reused cohort/fold procedure and previously selected settings;
training overlaps across folds and historical selection are not resampled. They
are not unbiased population generalization intervals. No trial-level bootstrap,
unsupported human p-value or independent external validation claim is made.

The four learned-method source means match M22's saved source-selection summaries
within1.12e-16. Input recording hashes, selected parameters and three source folds
agree. This is computational reproduction; it does not authenticate original M22
weights. Historical evaluation-role subjects were not loaded or retested. M22's
60.77% target band-power score describes a different, historically reused role
cohort and is not assigned to this new source-only release or external dataset.

## External acquisition and transfer

The metadata-only audit covers BNCI2014-001, Cho2017 and BNCI2014-004. Upstream
BNCI MAT distributions are unversioned; the distinct NEMAR001 mirror is v1.0.3.
BNCI licenses identify CC BY-ND4.0. Cho primary DataCite records CC0-1.0, while the
MOABB catalog discrepancy remains recorded. These notices do not establish consent
or every intended use. Acquisition was not authorized; external reviewed evidence
and aggregate-export clearance remain unavailable.

Authentic new fitted state now exists, but exact external input comparability does
not. Reference pools, sampling, timing and unit/feature conventions require review;
BNCI004 lacks six required channels. Harmonized transfer needs a new sealed design,
and external refitting remains a separate experiment. No human external confidence
interval, p-value, performance difference or empirical spectral/covariance shift
exists. See the acquisition and frozen-transfer readiness documents.

## Verification and remaining limits

The full cached suite passed1,453 tests, preserving all1,420 originals. The new33
archive tests also pass with network sockets forbidden. Frontend36 tests preserve
the original34. Ruff, formatting and strict mypy pass for271 source files. The
verification addendum records installed packages, all16 SDK examples, Playwright,
reproducible builds, security and actual private GitHub CI/publication evidence.

Synthetic four-platform checks validate independently fitted fictional releases,
not universal portability of these human weights. Independent human scientific
review, future dataset authorization, real external adapter validation, anatomical
validation beyond prior milestones and independent biological replication remain
open. No Milestone25 work was started.
