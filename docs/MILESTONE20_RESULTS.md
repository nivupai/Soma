# Milestone 20 results — Soma 0.20.0

Baseline: sanitized main `459474dcff90d369a0f3473148f5d700abd96c54`, with 1,161
passing Python tests. Work uses `feature/milestone20-human-data-adapters`; the old
unsanitized checkout is not used. Historical experiments/configurations and tests
are preserved. No scientific estimator, preprocessing algorithm or cache semantics
is replaced.

## Identity, permission and registration evidence

New identity, permission, plan, execution, comparison and audit-view schemas use
v1.0.0. M19 protocol/seal v1.0.0 and M17 result schemas 1.0.0/1.1.0 are preserved.
Dataset/version, keyed dataset-scoped subject, explicit nullable session/run,
modality/task, source evidence, acquisition/reference metadata and availability are
separate. No file-name chronology or cross-dataset participant linkage is invented.
Private mappings are verified in memory before dispatch; keys never enter workflow
inputs, caches, graph metadata or native execution records.

Permission checks are purpose/action/content-bound, retain unknown/conflicting/
revoked/expired evidence, and deny raw/participant-record export. Source access,
research-use support, consent, identity consistency, protocol conformance, external
registration, statistical validity and anatomical validity remain separate evidence.
The checks do not establish legal authorization or individual consent.

External registration is opt-in and read-only. No Soma registration ID was supplied
or created. Public OSF metadata matching is partial because editable descriptions
do not attest immutable protocol content at the source registration timestamp.
Immutable attachment/version attestation is not implemented. External preregistration,
human confirmation and longitudinal reliability remain unverified/unauthorized.

## Actual local coverage

The cache contains 65 EEGBCI subject directories, 18 IBSR subject directories,
five MRBrainS labeled training cases, and one ds000114 participant with two cached
motor-task sessions. MNE sample cache presence was inventoried; its local research-use
evidence was not established and no MNE sample pilot was requested or run.

| Pilot | Dataset-scoped subjects inspected | Explicit sessions | Selected records | Complete | Blocked |
| --- | ---: | ---: | ---: | ---: | ---: |
| EEGBCI | 2 | Not provided | 2 | 2 | 0 |
| IBSR | 2 | Not provided | 2 | 2 | 0 |
| MRBrainS training | 5 | Not provided | 5 | 0 | 5 |
| ds000114 | 1 | 2 | 2 | 0 | 2 |

These are ten dataset-scoped participant identities, not proof of ten different
people across datasets. All eleven scheduled records remain represented. No selected
participant was dropped after observing outcomes. Existing EEG trial/window QC
rejections remain in private native records; trials are not counted as participants.

EEG uses established unilateral-imagery preprocessing, events, QC and spectral
summaries for cached run 4. The official PhysioNet license source supports this
limited software policy; the source snapshot/hash and scope remain local.

IBSR uses fixed M10/M11 intensity predictions and independent provided reference
labels, matching native geometry/ontology and existing physical metrics. Metric
rows were inspected: CSF performance remains poor, while GM/WM overlap is higher.
Pipeline completion is not good segmentation accuracy. No threshold was tuned using
these outcomes. Upstream skull stripping/annotation uncertainty remain limitations.
Per-subject metric rows and native input fingerprints stay private.

MRBrainS Readme/manifest and training resource metadata were inspected. They provide
no sufficient agreement for this intended evaluation, so all five records are
blocked. This training subset was previously used in development/evaluation and is
not a fresh holdout. Hidden test file names may be counted (75 local files); hidden
test headers, payloads, references and hashes are not opened.

ds000114's local description declares CC0, separately from scientific readiness.
The two explicit fingerfootlips sessions have checked entities, task metadata, TR,
events and structural correspondence. Compatible audited preprocessing/transform
evidence is unavailable. Both records are blocked; no raw human GLM, inferred
preprocessing QC, reliability result or confirmatory claim is produced.

## Verification

- Full local Python suite: 1,234 passed, including all 1,161 baseline tests and 73
  new identity/governance/adapter/numerical/API tests; 117 existing dependency/model warnings.
- Frontend: 26 passed; TypeScript, ESLint, formatting and production build pass.
- Browser: all 13 local tests pass (12 preserved plus one new). The installed-wheel backend
  repetition also passed; demo and configured local-mode screenshots were inspected.
- Fresh noneditable wheel, sdist and source installs pass core/Explorer smoke checks,
  all twelve SDK examples each, and dependency checks from isolated directories.
  Wheel/sdist member audits and two byte-identical fixed-epoch builds pass.
- Strict mypy checks 238 source files. Ruff, formatting and diff checks pass.
- All 229 baseline test/configuration/experiment/frontend-test hashes are unchanged.
- Gitleaks 8.30.1 scanned proposed files and reachable sanitized history: no material
  secrets, restricted data or personal home paths; only the 65 existing exact-file
  reviewed false positives, no new exceptions or rule suppression.
- A proposed key-passing design was rejected by automatic review before application.
  The implemented in-memory mapping verification and regression tests avoid passing
  keys to the workflow engine entirely.

Public metadata tables contain operational counts only. Participant mappings,
per-subject scientific outputs, private authorization configurations, keys, agreement
contents and screenshots remain ignored local files. No raw medical data, model
weights or participant-specific images enter Git.

## Cross-platform and publication addendum

The existing 13-job matrix is retained, with actual macOS arm64/Linux x86_64
Python 3.11/3.12 fictional identity/evidence/schema tests and unchanged M17/M18/M19
scientific checks. CI requires no human datasets and cannot establish equivalent
human-data access or rights across platforms. Actual run evidence will be added
after the private PR checks complete; local tests do not substitute for that matrix.

## Remaining limitations

This is a bounded, previously inspected pilot, not population validation or a new
prospective study. Public/local notices and operator assertions are not independent
legal/consent attestations. Acquisition chronology is not verified in these real
records. MRI tissue metrics do not validate skull/scalp conductors or cortical
source accuracy. MRBrainS use evidence and ds000114 preprocessing/transforms remain
missing. Registration attachment immutability and independent content-time attestation
remain unsupported. No numerical tolerance was widened or prior assertion weakened.

Proposed Milestone 21: independently attested immutable registration attachments and
reviewed authorization/preprocessing bundles for carefully scoped longitudinal human
validation. Milestone 21 has not been started.
