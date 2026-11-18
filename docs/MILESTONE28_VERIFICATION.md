# Milestone 28 verification addendum

The v0.27.0 baseline was reverified before implementation: 1559 Python tests,
42 frontend and 20 configured browser tests, three fresh-install receipts with
19 examples and 297 matching payload files, 13/13 PR and postmerge jobs, and ten
four-platform comparison families. Local main matched PUBLIC github/main at
31e389db42c5cd3bfd2bca0e0a83958257744fcf. Historical protected file/archive hashes
are preserved. The exact original discrepancy was reproduced before adapter work.

The physical design was committed at 61973db before the original comparisons.
Post-outcome revisions 2/3 correct inherited descriptive metadata and generic
summary-axis scope; original seals and outcomes are retained. The final full
repeat includes heldout head5 and compares the unchanged numerical tables.
No claim of pre-outcome timing is made for these corrections. No 10% threshold,
source subset, scalar normalization or inverse regularization was selected from
results. Current tests add adversarial physical-contract, independent analytical,
reference, ordering, source/sign/unit and integrity checks without altering prior
tests. Full/offline tests, frontend/browser, Ruff/format, strict mypy, package,
dependency/security and cross-platform checks are recorded in the public
verification JSON. Large studies remain outside ordinary CI. The existing 13-job
matrix retains ten comparison families and adds a small matched homogeneous
MNE/OpenMEEG physical comparison as an eleventh family, not a new acceptance gate.

All figures are generated from real synthetic numerical outputs and visually
inspected. Independent direct-sum norms and SciPy correlations verify adapter
metrics; exact sphere gradients are checked against a separate Legendre finite
difference implementation. The native envelope is read back and its identities
checked. Archived executed source hashes are retained; invalid-input/style/SDK
corrections after the run do not change the physical assembly or numerical data.
The first expanded unit test for millimetres failed because the existing Points
constructor correctly rejected the bad values before the test's exception context;
the new test now checks that actual rejection point. No prior assertion was changed.

Privacy scans cover tracked working files and reachable history with unchanged
Gitleaks rules and exact-content historical false-positive review. No human anatomy,
EEG, restricted phantom data, credentials, private paths or model weights are release
inputs. .gitignore exclusions and historical/M24 archive hashes are rechecked.
Three fresh noneditable wheel/sdist/source installations must pass core/Explorer,
20 SDK examples and payload equality; deterministic builds are compared bytewise.
Optional OpenMEEG is audited in addition to the core/Explorer dependencies.

PR checks must pass at the intended head before merging. Postmerge CI is verified
separately, with four actual platform bundles downloaded and all eleven comparison
families rerun. The final PR/completion receipt records actual run URLs and merge
SHA, clean synchronized main and PUBLIC visibility. No force push or historical
rewrite is used. Scientific three-layer agreement still fails despite passing
software gates; independent four-layer/FEM/phantom/human validation is not inferred.


## Security gate blocked on 2026-11-17

The full local suite passes 1604 tests (45 added); the offline selection has
1587 tests. Frontend tests pass 44 and configured Playwright passes 21.
Python dependency auditing reports no known vulnerabilities in auditable packages;
the local project itself has no PyPI audit record.

The unchanged frontend toolchain resolves picomatch 4.0.7 through Vite, Vitest
and globbing utilities. `npm audit --audit-level=moderate` now fails with 11
high-severity dependency entries caused by GHSA-fc5q-39xc-vjpf / CVE-2026-112366.
The [reviewed upstream advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
was updated on 2026-11-17 and lists affected versions through 4.0.7 with no
patched release. The [upstream release list](https://github.com/micromatch/picomatch/releases)
and npm registry still identify 4.0.7 as latest at this audit.

This is an unresolved toolchain dependency vulnerability, not a scientific test
failure or a material-secret finding. It is not suppressed, relabeled as a false
positive or bypassed. No forceful dependency downgrade, matcher substitution or
CI audit relaxation is used. Publishing a reviewable PR does not authorize merge:
M28 must remain unmerged until the required security/Explorer gate passes. No
postmerge CI result or M28 main commit can be claimed while that gate is blocked.
