# Milestone 21 results — Soma 0.21.0

Baseline: sanitized private main `7ed815b72015416ba76cc470a942a837b3f677b9`,
1,234 passing Python tests, 26 frontend tests and13 browser tests. The baseline
was reverified before implementation. Work uses `feature/milestone21-research-readiness`.
The old unsanitized checkout is not accessed. Historical reports and scientific
assertions are preserved.

## Architecture plan and implementation

1. Extend M20's provider-neutral registration transport with exact native OSF
   attachment/version/hash correspondence, preserving the old metadata inspector.
2. Use existing canonical hashing and M19 protocol fingerprints for immutable
   evidence-reference bundles; keep private documents and locations separate.
3. Wrap M14 geometry, ITK transforms and measured confound QC with typed,
   content-bound, explicit-root preprocessing imports. Do not execute fMRIPrep.
4. Feed these checks into existing sealed human plans as individual readiness gates.
   Keep M20 execution/inference restrictions. Use M17 native result I/O for receipts.
5. Extend the existing Explorer Data Audit, SDK and Typer commands, and use fictional
   fixtures in the retained four-runner/thirteen-job CI architecture.

Evidence bundle, attachment, preprocessing manifest/audit, session audit, readiness
policy/report schemas are1.0.0. Existing result/protocol/identity schemas and numerical
algorithms remain unchanged. Human review assertions are not issuer authentication,
legal authorization or participant consent.

## Actual evidence and cached pilot coverage

No actual accessible registration/attachment was supplied. Actual externally verified
registrations: **zero**. Concrete OSF support is bounded to the exact current revision
of a native registered file with full supported source metadata/hash/timing. Editable
descriptions, older versions/add-ons, private/authenticated access and incomplete
archives cannot establish immutable correspondence.

| Dataset | Scoped subjects | Reviewed records | Outcome |
| --- | ---: | ---: | --- |
| EEGBCI | 2 | 4 | Existing descriptive analyses complete; repeated runs, no documented visits |
| IBSR | 2 | 2 | Existing independent-reference tissue results reviewed; poor CSF preserved |
| MRBrainS | 5 | 5 | Existing blocked training cases retained; no new authoritative agreement |
| ds000114 | 1 | 2 sessions | No compatible derivatives in either configured location; blocked |

These are ten dataset-scoped identities, not proof of ten different humans. EEG uses
cached runs4 and8 of unilateral imagery, fixed existing preprocessing and event/QC
semantics; trials are not participants. QC output rows remain private. IBSR source/
reference identity, geometry, ontology and fixed prediction provenance were rechecked
against existing results without retuning or recomputing segmentation. Its tissue
metrics do not validate skull/scalp BEM geometry or cortical source accuracy.

No new authoritative MRBrainS agreement appeared. Its five previously inspected
training cases remain blocked and are not a fresh holdout; no hidden test references
or new MRBrainS MRI payloads were opened. The two raw ds000114 sessions remain
technically inspectable under existing software-use policy but lack current BIDS/
preprocessing provenance, transforms, motion/DVARS/SDC/QC and chronology evidence.
The precise private gap report and documented fMRIPrep 25.2.7 external handoff do not
claim an executed pipeline. No Docker install, container pull, large data download,
new human GLM or confirmation was performed.

New reviewed human authorization bundles were not supplied. Local public notices
continue supporting only the existing limited software policy; M21's additional
review requirements remain explicit. **Previously blocked records newly unblocked:0.**
All three current readiness reports remain BLOCKED; MRBrainS's prior blocked status
is retained without fabricated fresh validation. No longitudinal reliability is claimed.

## Verification

- Full local suite: **1,331 passed**, including all 1,234 baseline tests and 97 new
  offline/adversarial/numerical/SDK/API tests; 117 existing dependency/model warnings.
- The 97 new tests also pass with network connections forbidden.
- Frontend: 30 passed (26 baseline plus4 new); TypeScript, lint, formatting, build
  and npm audit pass. Browser: 14 passed, none skipped, against the fresh noneditable
  installed backend; demo and configured two-session audit screenshots inspected.
- Strict mypy: 243 source files. Ruff, Python formatting and dependency checks pass.
- Fresh wheel, sdist and source installs pass isolated core/Explorer checks and all
  thirteen SDK examples each. Distribution member inspection and two independent
  byte-identical fixed-epoch builds pass. Pip audit reports no known vulnerabilities
  (the local unpublished Soma version is not an audited PyPI distribution).
- All 239 preserved historical test/configuration/experiment/frontend file hashes
  match, including all229 paths tracked by the previous preservation receipt.
- Gitleaks8.30.1 scans the complete proposed tree and reachable sanitized history:
  no material secrets, restricted data or personal home paths; only the65 existing
  exact-file-reviewed false positives, with no new exceptions or suppressed rules.
- Browser checks caught a duplicate readiness panel; its regression test now verifies
  a single panel. The runner rejects readiness-only policies before any dispatch,
  preventing new evidence requirements from being bypassed by the legacy entry point.

The existing thirteen-job/four-runner CI architecture is retained. Implementation
commit `07277fb59cf8214f5da2589ccb6dd2a9cdeed223` passed **13/13 jobs** in
[PR run42866196384](https://github.com/nivupai/Soma/actions/runs/42866196384).

Actual runner artifacts were downloaded and independently compared locally: macOS
arm64 Python3.11.9/3.12.10 and Linux x86_64 Python3.11.18/3.12.16. Fictional canonical
bundles, session relations, registration schema/status and blocked-gate invariants
are identical across all four runners and the local example. Existing numerical,
workflow, protocol and human-identity comparisons also pass their unchanged rules.
Generated numerical input-byte differences remain separately reported by the
inherited comparison; no cache interchangeability/full-study equivalence is claimed.

Compact evidence is retained in `experiments/milestone21/ci-evidence.json` and
`cross-platform-readiness.json`. No human datasets, actual registrations or private
agreements were accessed by CI. Existing numerical tolerances and historical
scientific assertions are retained. This documentation/evidence addendum must pass
all thirteen checks again on its exact feature head before merge. Final merge,
post-merge CI and synchronization receipts remain in ignored local reports and the
completion message.

## Scientific limitations and next evidence

File hashing establishes correspondence, not truth or authority. OSF provider-attested
immutability is not a cryptographic timestamp authority or proof of prospective study
design. Authentic authorization/consent, actual human preprocessing quality, common
anatomical space/task implementation and noise-model adequacy remain separate gaps.
The existing fMRI execution gate is not removed by parsing a new manifest.

Proposed Milestone 22: review an actually supplied immutable protocol attachment and
an authorized, externally executed preprocessing bundle, including independent
common-space/task correspondence and longitudinal QC review. Milestone 22 is not started.
