# Milestone 25 results — authorized acquisition controls, human execution BLOCKED

Soma v0.25.0 makes progress through a permission-bound acquisition procedure,
content-addressed snapshots, final frozen harmonization proposals and a preserved
runtime bridge to the genuine M24 models. No human target data were acquired,
parsed, fitted or evaluated. No M24 model was changed or overwritten.

## Dataset decision and actual coverage

No candidate is selected for human execution. Cho2017 is preferred for the next
exact-distribution rights/manifest review because its primary DataCite record
identifies CC0-1.0; the catalog CC BY4.0 discrepancy and consent/authorization
questions remain unresolved. BNCI001 remains the most documented primary feasibility
audit, but its original CC BY-ND4.0 aggregate-export review and reference mismatch
remain blockers. BNCI004 also reports CC BY-ND4.0 and lacks six required channels.
NEMAR nm000139v1.0.3 is a separate distribution from unversioned upstream BNCI MAT.

| Quantity | Actual outcome |
|---|---|
| Acquisition approval |NOT_GIVEN; no reviewed complete external M20/M21 bundle |
| Expected checksums/sizes |Incomplete; proposed manifests cannot authorize acquisition |
| New human recordings |0 |
| Human external subjects/sessions/trials |0/0/0 |
| Human external balanced accuracy |NOT_AVAILABLE |
| Human uncertainty/p-values |NOT_AVAILABLE |
| Learned source components refitted |0 |
| Missing-channel interpolation |Forbidden |
| Exact / harmonized human transfer |BLOCKED or NOT_COMPARABLE; no input-shape shortcut |

The [authorization report](EXTERNAL_EEG_AUTHORIZATION_V25.md) specifies provider
URLs, versions, expected file counts and actionable approval/checksum requirements.
No website terms were accepted and no private credentials were used. Public rights
metadata do not establish consent. Selection did not inspect new target outcomes.

## Genuine archived-model control

M24 release `8ce2e0952dce6f770a15ae70b99863d8712ec3017de951bba37bf3ef070afe85`
contains five complete source-fitted families from 35 historical EEGBCI subjects.
The M25 controller verified capsule integrity and used the preserved noneditable
v0.24 runtime/dependency snapshot. Original source/build/environment guards were
preserved; no guard was relaxed to run the models under a new installation.

The source-only reproduction control matched all 1,441 original labels and decision
scores per family exactly, with maximum error 0. Supported probabilities also matched
exactly; MDM probabilities remain unsupported. All archived files remain byte-identical.
This checks preserved state and runtime orchestration; it is not new source-cohort
accuracy, recovered M22 weights, external inference or biological replication.
See [the runtime report](FROZEN_EEG_RUNTIME_V25.md).

## Harmonization and observable shift

The new M19 proposal seals bind immutable model identity, candidate/input-manifest
identity, mode and scientific policy. Complete input hashes require a fresh seal
before execution. Technical proposals are fixed without external accuracy search.
BNCI001 declares 250→160Hz, microvolt conversion, cue-relative epochs and source
artifact/QC policy, but the 22-versus-64 reference operator remains incompatible.
Cho's original reference/unit/cue conventions remain unverified. BNCI004's three
bipolar channels cannot satisfy the frozen nine-channel model. Exact and harmonized
modes remain distinct, with no target scaler/filter/reference/classifier fitting.

Only metadata shift is established for human candidates: sampling, nominal montage,
reference hardware, timing and session structure. Human spectral/covariance changes,
artifact burden, error/confidence distributions and physiological explanations are
not observed. No deterioration or improvement is invented.

## Numerical and statistical controls

Independent fictional targets use seed 25042, distinct from source seed 23042, with
separate dataset-scoped trial/session identities. The positive test evaluates five
frozen synthetic models on 9 fictional participants/2 sessions/648 trials. This is
explicitly SYNTHETIC_TEST_ONLY and has zero human external coverage. It verifies
immutable prediction, participant-level aggregation and rejection behavior; it is
not missing human evidence. Source/target refitting is absent. Missing people and
model failures remain missing; partial coverage is not called complete validation.

The participant is the uncertainty unit. Session/run cells are averaged within
participants; confusion matrices are labeled descriptive pooled counts. Small-N
conditional intervals are not broad population precision. No unsupported human
exchangeability/significance test is reported. M22/M24 are different estimands:
the historical M24 source-fold band-power mean60.50% is not an external result.
The comparison API refuses mismatched dataset/protocol/model/manifest/mode identities
and never authorizes scientific cache interchange.

## Verification and publication limits

The final full cached suite passed 1,487 tests, preserving all 1,453 baseline tests.
The new 34 adversarial tests also have a dedicated offline gate. Frontend 38 tests
preserve the original 36. The [verification addendum](MILESTONE25_VERIFICATION.md) records browser checks,
all 17 installed SDK examples,
quality, dependency audits, reproducible packages and complete privacy/history scans.
Historical scientific artifacts/tests and every M24 archive file are checked by hash.
Only aggregate metadata/control facts enter Git; real data, model parameters,
participant rows, probes and permission evidence stay ignored and private.

Preflight PR#9 is merged at `6229bf03a292399fff8041d2b6467d7f73dadebc`.
Its post-merge run 43008787792 still has 12 successful jobs and one comparison job
not started because of GitHub billing/spending limits. That gate remains pending.
M25's 13-job workflow preserves the eight prior comparison families and adds a ninth
synthetic family. If billing prevents required checks, its PR remains unmerged;
local comparisons do not substitute for remote CI. The completion report/PR record
actual run evidence and repository visibility. No Milestone 26 work was started.
