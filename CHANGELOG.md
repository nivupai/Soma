# Changelog

The detailed per-milestone announcements and command references that previously
lived in the README are preserved in [docs/MILESTONES.md](docs/MILESTONES.md).

## Unreleased

- Documentation only: README rewritten as a product front page; prior README
  milestone announcements moved verbatim to `docs/MILESTONES.md`; new
  `docs/DATA_POLICY.md` dataset inventory. No scientific code changed.

### M33 forward-model revalidation (workstream D)

- Add `soma.source.forward_revalidation` (geometry-preserving midpoint subdivision,
  fixed-normal projection, M32 relative-change metric, per-source agreement, margin
  strata, minimum-level rule, readiness tags) and `scripts/run_forward_revalidation.py`
  (resumable one-stage-at-a-time runner; private arrays under ignored `reports/`).
- MNE sample EEG, 7,598 oct6 cortical sources, fixed normals, M32 conductivities, all
  tagged QC_ONLY_ANATOMY / skull not CT-validated. Unrestricted refinement FAILS the 10%
  target (3→4 36.87%, 4→5i 21.48%), driven by sources within 1–2 mm of the inner skull;
  with a >=1 mm source margin (99.0% of sources) 4→5i is 6.94% and level 4 is the minimum
  human mesh level. MNE vs OpenMEEG: 32.92% (level 3), 25.43% (level 4); 7.53% at level 4
  with the >=1 mm margin; median per-source correlation 0.9999 at level 4.
  See `docs/MILESTONE33_FORWARD_RESULTS.md`.

### M33 cortical source space (workstream C)

- Add `soma.source.cortical`: white/pial midsurface sources per hemisphere, count-matched
  ico/oct decimation on the subject sphere, outward area-weighted normals and barycentric
  patch-area weights. Medial wall/named-label, orientation and inner-skull containment
  exclusions are counted by reason and region; excluded area is never redistributed.
- MNE sample (oct6, 5120-face BEM inner skull): 7,618 sources covering 94.43% of the
  midsurface area (99.59% after medial-wall exclusion), all inside the inner skull;
  19 candidates outside and 1 with normal opposing white->pial were excluded. Public
  aggregate in `experiments/milestone33/cortical-source-space-sample.json`.
- The volumetric `SourceDomain` (13.10% GM voxel coverage) is unchanged for comparison.

## 0.32.0 — MRI-derived head models and anatomical evidence

- Execute independent tissue-baseline replication on 18 IBSR and five MRBrainS training
  cases, preserving poor segmentation results and all historical scientific outputs.
- Add explicit scanner/surface/head geometry, MRI voxel-measure source priors and
  evidence-based conductor readiness; execute one real MRI-derived QC-only BEM workflow.
- Retain the failed coarse refinement target, missing conductor truth and limited
  source coverage. No human source-localization accuracy or compatible human FEM claim.
- Add public aggregate reports and an explicitly opted-in, loopback-only private MRI
  showcase; participant anatomy and image fingerprints remain outside public assets.
- Extend the four-platform mandatory software gate without changing native Gmsh policy.

## 0.31.0 — inverse priors and source-density calibration

- Add explicit integrated-moment covariance priors, spectral and independent-repeat
  regularization controls, with rank-aware whitening and analytical checks.
- Preserve M30 results; replicate original inverse-grid findings and publish a
  frozen six-head/96-source synthetic study, nested grids, conditional intervals,
  negative findings, point-spread diagnostics and twelve figures.
- Extend the existing Explorer with read-only, fingerprint-checked M31 results.
- Keep the M30 canonical gate and native diagnostic policy unchanged. A changed
  native signature already blocks the merged baseline; no release exception added.


## 0.26.0

- Frozen four-shell physical source uncertainty experiments with independent off-grid generators, paired noise, source-cluster intervals and retained numerical failures.
- Quantify skull boundaries/conductivity, electrodes, registration, interactions and grid sensitivity using existing Tikhonov/MNE/dSPM operators.
- Read-only Explorer compares executed synthetic maps with known truth; no human anatomical validation or new medical-data acquisition.
- Preserve all prior tests and cross-platform gates; publish only reviewed synthetic tables and vector figures.

## 0.21.0

- Exact current-revision OSF attachment evidence, sealed private-document references and reviewed permission readiness.
- Content-bound preprocessing imports reuse established geometry/ITK/confound QC; no pipeline launch or human inference.
- Explicit session/readiness gates, typed SDK/CLI and read-only Explorer extension.
- Bounded cached pilots retain missing evidence and prior restrictions; no newly unblocked human analyses.


## 0.20.0

- Add dataset-scoped human identities, explicit absent sessions, purpose-scoped use
  evidence and frozen-cohort conformance over existing scientific pipelines.
- Add bounded cached EEGBCI/IBSR pilots, blocked MRBrainS/ds000114 records, native
  lineage, SDK/CLI and read-only research-data audit views.
- Add opt-in public registration metadata inspection with explicit mutable-metadata
  limits; no automatic registration, preregistration or inference promotion.
- Preserve existing scientific algorithms, schemas, cache semantics and historical tests.

## 0.19.0

- Add strict versioned scientific protocol declarations, immutable local seals and
  explicit parent amendments; no external preregistration or confirmation claim.
- Bind registered workflow requirements to exact, controlled and exploratory replay;
  retain missing units and classify seven drift categories with frozen tolerances.
- Add SDK/CLI, read-only Explorer comparisons, four synthetic execution histories,
  independent synthetic MRI reference metrics and actual cross-platform CI checks.
- Preserve historical scientific reports, algorithms, result schemas and cache policy.

## 0.17.0

- Add strict versioned scientific envelopes, domain contracts and bounded non-pickle arrays.
- Add explicit semantic compatibility, SI-prefix conversion and read-only legacy migration.
- Extend Explorer/CLI/SDK with schema, integrity and migration status while retaining inference guards.
- Add analytical cross-platform cases and dependency-floor verification; no new estimators or human validation claims.

## 0.16.0

- Add explicit `soma.sdk` imaging, EEG, source, fMRI, provenance, synthetic and
  optional Explorer interfaces while preserving existing module imports.
- Add identity/grid checks, voltage validation, undeclared-label rejection and
  conservative result metadata compatibility checks. Preserve inference policy.
- Ship the compatible local Explorer gateway and small policy resource in wheels;
  add `soma-explorer`, typed marker and reviewed source distribution selection.
- Add eight synthetic examples, distribution privacy checks and fresh noneditable
  core/Explorer installation verification. Keep scientific dependencies compatible.
- Correct NumPy typing boundaries across Python3.11/3.12 without changing formulas.
- Separate CI quality/science/packaging/Explorer/security jobs with pinned actions
  and read-only permissions. No public release, PyPI upload or deployment.

Historical scientific reports and original release records are preserved.

## 0.18.0

- Add opt-in typed workflow lineage, exact-environment identities and verified caches.
- Add atomic publication, fault-tested recovery and four existing-method synthetic DAGs.
- Add metadata-only interactive workflow inspection and actual cross-platform replay.
- Preserve existing scientific algorithms, result schemas and historical tests/artifacts.

## 0.22.0

- Add sealed, permission-aware cached EEG decoding evaluation with five existing
  estimators, source-only selection, run-held-out and subject-disjoint fitting,
  subject bootstrap intervals, ten prespecified sensitivities and separate adaptation.
- Add auditable native cells, aggregate-only SDK/CLI/Explorer reporting and actual
  historically reused EEGBCI results; no independent external replication claim.
- Add adversarial/numerical/synthetic benchmark tests and four-runner reproducibility
  artifacts; preserve existing estimators, inference guards and historical reports.

## 0.23.0

- Audit BNCI2014-001 permissions, local availability and original M22 model fidelity;
  report human external evaluation BLOCKED instead of inventing replication.
- Add sealed external plans, prediction-only numeric model capsules, explicit MAT
  handling and separately labeled fixed-parameter external refitting with existing methods.
- Extend the SDK, CLI and Explorer with compatibility, shift and blocked-state reporting.
- Add adversarial/numerical/offline tests and four-platform fictional transfer evidence;
  preserve prior scientific estimators, tests, protocols and outputs.

## 0.24.0 — prospective fitted-model archives

- Add sealed source-only EEG model releases binding complete M23 numeric state,
  source fingerprints, prediction semantics and private verification probes.
- Train new EEGBCI source-role models; retain original M22 outputs and distinguish
  numerical reproduction from independent external validation.
- Add strict release inspection, prediction-only reload verification, fixed
  source-fold summaries, focused SDK/CLI and a read-only Explorer model panel.
- Add metadata-only external acquisition/compatibility plans; acquisition and
  human external inference remain blocked. No human weights are distributed.

## 0.25.0 — controlled external EEG validation readiness

- Add explicit manifest-bound acquisition approval, bounded checksum-verified HTTPS
  transport, immutable snapshots and candidate-specific frozen harmonization seals.
- Verify the authentic unchanged M24 release through its preserved runtime without
  refitting, environment overrides or claims of recovered M22 state.
- Add independent fictional target evaluation, participant-level failure/missingness
  controls, focused SDK/CLI and read-only Explorer approval/compatibility states.
- External acquisition and human inference remain BLOCKED without required evidence.
  Preserve outstanding billing-blocked CI gates and leave unverified PRs pending.


## 0.27.0 — Nonspherical BEM validation

- Frozen six-head/four-interface synthetic study with three estimated meshes and finer off-grid truth; independent reference hierarchy and explicit failed three-layer agreement gates.
- Conditional hierarchical source/head intervals, full retained case accounting, physical/geometry diagnostics and auditable synthetic figures/tables.
- Optional pinned OpenMEEG adapter, SDK/CLI and existing uncertainty workbench extension; no FEM, human anatomical accuracy or empirical phantom claim.


## 0.28.0 — Independent BEM discrepancy diagnostics

- Reproduce and preserve M27 disagreement; freeze canonical geometry, source/sensor/reference and numerical factor controls before evaluation.
- Quantify analytical limits, solver/refinement/source/orientation effects and inverse consequences; retain failed 10% agreement gates without scalar rescue.
- Extend SDK/CLI and existing synthetic-only Explorer workbench, with auditable tables, figures, native receipts and independent metric checks.

## 0.29.0 — independent four-layer FEM reference (dependent PR, not merged)

- Add optional scikit-fem12.0.2 full-subtraction P1 reference, conforming material
  tetrahedra and independent concentric harmonic transmission controls.
- Retain the frozen10% gate and all failed configurations; compare six M27 heads
  at three resolutions and investigate M28 with heldout three-layer controls.
- Export physical field, mesh, uncertainty, inverse, provenance and figure data;
  extend the synthetic-only Explorer, SDK/CLI and small cross-platform checks.
- Preserve all M28 artifacts; keep PR13's npm security audit blocking dependent merges.

## 0.30.0 — independent mesh and source-grid study (dependent, unmerged)

- Add optional official Gmsh 4.15.2 native meshing with material/facet/volume audits;
  preserve M29 radial and M28 scientific artifacts and all frozen targets.
- Compare shared and separately sampled boundaries across six synthetic heads;
  retain failures and distinguish geometry from discretization effects.
- Evaluate 12/33/147/341 inverse candidates under paired signals and frozen settings;
  report lower bounds, non-monotonic errors, uncertainty, PSFs and resolution data.
- Extend the read-only workbench and SDK/CLI without new frontend packages.
- Keep upstream npm audit blocking all dependent merges.
