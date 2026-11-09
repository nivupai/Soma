# Milestone 14.1 results addendum

Soma0.14.1 continues baseline `8e24b6e`/0.14.0. Historical scientific reports and
all815 original tests are preserved. The exact historical null was reproduced
before code changes; subsequent diagnostics use independent, frozen streams.
No Explorer, Milestone15, cohort expansion, push or MRI download occurred.

## Verification and implementation

- Baseline:815 passed. Final full suite:851 passed,98 warnings;36 new tests.
  Ordinary offline suite:834 passed,17 integration tests deselected,96 warnings.
  Warnings include existing scientific diagnostic warnings and Nilearn warnings;
  they are not silently suppressed. Full-suite wall time85.33s; offline timing
  is recorded in the aggregate receipt and private logs.
- Ruff check and formatting pass; strict mypy passes184 source modules;
  pip check reports no broken requirements. No dependencies added.
- All54 original test files and885 historical report files match the pre-change
  SHA256 ledger. The private ledger and medical hashes remain ignored.
- Independent whitened QR/precision checks validate coefficients, covariance,
  t and p; actual FirstLevelModel images agree with bounded matrix diagnostics
  for OLS/AR1/AR2. Tests cover rank errors, short samples, AR covariance, RNG
  independence, correction arithmetic, deterministic outputs and policy refusal.
  Existing preprocessing tests continue to cover confound/session/space failures.
- The new readiness adapter retains inherited dataset events, gates on official
  input validation and never executes or downloads. Versioned fMRIPrep parser
  inspection replaced obsolete longitudinal syntax. Method-specific BY and
  Bonferroni map labels are explicit; default BH numerical behavior is preserved.

## Statistical findings and supported policy

Original global-null any-BH rejection **100%,23%,24%** for OLS/AR1/AR2 is exactly
reproduced with the same100 historical seeds. There is no demonstrated incorrect
p conversion or multiple-testing arithmetic. OLS uses an invalid temporal-noise
assumption under AR(.6). Feasible AR estimates are biased at short n and treat
estimated covariance as known for nominal Student-t inference; independent
stationary feasible GLS also undercovers. Startup, spatial dependence and AR2
clustering cannot be assigned a single exclusive causal fraction from this audit.
Full structured diagnosis: `FMIRI_NULL_CALIBRATION_AUDIT.md`.

New n100/m343 independent AR(.6) null,128 families: any BH rejection is99.22%
OLS,16.41% AR1 (Wilson95[10.99%,23.78%]),17.19% AR2 ([11.63%,24.65%]),2.34%
known GLS ([0.80%,6.66%]). Iid OLS is5.47% ([2.67%,10.86%]); fitting feasible AR
to iid errors instead gives15.63%/21.88%. New fixed-design experiments are
controlled diagnostics, not relabeled historical repetitions.

At n100 single AR(.6) voxel,512 replications, AR1 rejects6.64% and95% coverage is
93.36%; known GLS4.30% and95.70%. At n40 AR1 rejection13.67%/coverage86.33%.
Under the signal/null mixture, BH empirical FDR is.29076/.07354/.07680/.04395
for OLS/AR1/AR2/known GLS, with replicate bootstrap uncertainty in the aggregate
receipt. Tests across voxel counts and spatial correlation/smoothing are retained.
BY/Bonferroni lower rejection but do not validate invalid marginal probabilities.

Default outputs are descriptive/experimental nominal tests. Explicit unsupported
confirmatory requests fail; effects, uncertainty maps and diagnostics remain.
The narrowly allowed synthetic contract is fixed-design/mask, independent iid
Gaussian errors, OLS, no smoothing, n100/m1,27,343 and two-sided BHq.05 with
explicit declared assumptions. This is not a noise classifier or human guarantee.
Feasible AR and human confirmation remain unsupported. Final policy/evidence/code
hashes are frozen before the attempted human gate. No arbitrary df correction or
simulation tuning was used to make rejection rates look nominal.

## Human readiness, execution and incomplete criteria

Existing ds000114 coverage remains one participant, two motor-execution sessions,
two BOLDs and two T1w references, inherited events. Official local BIDS validation
passes unchanged raw input with111 warnings/seven code classes; raw version and
validator schema fields are recorded separately. No field maps or phase-encoding
direction, derivatives, transforms or confounds are available.

Docker client exists but daemon is unavailable; ARM host/amd64 image compatibility
and VM resources are unverified. Host RAM16GiB, free disk about34.7GiB at audit.
Pinned fMRIPrep25.2.7 remote digest is recorded; no local-image claim or layer pull.
FreeSurfer license and complete TemplateFlow/anatomical assets are absent or
unverified. An exact offline, read-only-raw command and all blockers are in
`FMIRI_PREPROCESSING_SETUP.md` and the private generated plan.

**fMRIPrep was not executed.** Preprocessing QC and HTML/anatomical registration
review are unavailable. Existing audit rejects both sessions as ineligible;
zero human models, contrasts or retest metrics were calculated. No cohort ICC.
The human acceptance criteria G/H remain incomplete pending resources and actual
QC. The joint unbiased anatomical-reference plan must not be interpreted as
held-out-visit preprocessing. Motor execution does not validate motor imagery.
Anatomical registration, skull/scalp conductor accuracy and multimodal localization
remain separate unvalidated questions; tissue or BIDS consistency is insufficient.

## Artifacts, cost and limits

The final experiment contains19,456 diagnostic records; exact X/c/temporal and
spatial covariance arrays, p-values, per-condition tables, three PNG figures and
underlying NPZ arrays were generated and inspected. No pickled object arrays or
nonfinite numerical arrays are accepted. Manifests validate output hashes and
actual source code, including the baseline Git source for historical reproduction.
Aggregate evidence and scripts are under `experiments/milestone141/`.

Final null-audit wall time **98.41s**, CPU97.19s and peak RSS **376.53MiB**
are recorded in `verification.json`
(process high-water including imported libraries, not incremental allocation).
Three plots show marginal tails, family errors, coverage/SE and spatial/mixture
FDR. Their numerical inputs are preserved. The private source/config hashes,
versions, seeds and supplemental historical reconstruction receipt support audit.
Full synthetic reports and all individual medical inventories/results stay ignored;
only aggregate receipts, nonidentifying code, config and documentation are committed.

Remaining statistical limits: finite Monte Carlo precision (particularly rare
family tails), bounded synthetic Gaussian models, fixed masks/design family,
no universal finite-sample feasible-GLS calibration, incompletely separated AR2
clustering/tail mechanisms and no validated real-human inference. Human execution,
registration/transform QA, missing-SDC decision and descriptive two-visit analysis
remain unavailable. This addendum records those gaps rather than claiming an
executed preprocessing pilot.
