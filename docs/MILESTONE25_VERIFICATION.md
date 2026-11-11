# Milestone 25 verification addendum

This addendum records v0.25.0 verification without rewriting earlier milestone
reports. Local execution used macOS arm64, Python 3.12.2, one numerical thread and
ignored local receipts. Remote checks are a separate publication gate.

## Scientific and interface checks

| Check | Actual local result |
|---|---|
| Full pytest | 1,487 passed; 117 warnings; all 1,453 baseline tests preserved |
| Dedicated offline acquisition/validation tests | 34 passed |
| Protected prior tests/configurations/experiments | 299 files unchanged by SHA-256 |
| Frontend unit tests | 38 passed, including the original 36 |
| Playwright | 18 passed, including the original 17 |
| TypeScript, ESLint, Prettier and production build | Passed |
| Ruff lint / format | Passed; 609 files already formatted |
| Strict mypy | Passed, 276 source files |
| Source SDK examples | All 17 completed |
| Isolated wheel, sdist and source installations | Core + Explorer smoke checks and all 17 SDK examples; receipts retained locally |
| Main environment dependency consistency / vulnerability audit | No broken requirements / no known vulnerabilities in auditable dependencies |
| Frontend dependency audit | 0 vulnerabilities |

Warnings include existing scientific-library/deprecation warnings and the Vite
chunk-size advisory. They are not concealed or treated as scientific validation.
The package itself has no PyPI audit record; dependency scanning is not an audit
of Soma's own implementation.

The new offline example uses independent fictional target draws (seed 25042),
9 fictional participants and 648 trials across two sessions. Five models have
complete coverage, the dummy control is 0.5, and the declared synthetic signal
checks pass. These are synthetic controls, never human external outcomes.

## Preserved authentic archive

Release `8ce2e0952dce6f770a15ae70b99863d8712ec3017de951bba37bf3ef070afe85`
was inspected before and after execution: all 46 archived files are byte-identical.
The code-owned worker under the preserved noneditable v0.24 environment reproduced
1,441 source-probe labels and decision scores per family exactly. Supported
probabilities also had maximum absolute error zero; MDM does not expose them.
The worker hash is
`2a1d34bbe67e749f21678e28dd12b05dae29ca2f34671771bf60b9f3a5e3f635`.
No learned component was refitted. This is SOURCE_RELOAD_ONLY, not external accuracy.

The three final candidate protocols are planning revision 2 / protocol 2.0.0.
An earlier uncommitted draft incorrectly assigned a presumed target feature
contract to unverified distributions. It was corrected before human acquisition
or outcome inspection; the superseded drafts remain in ignored audit storage.
Cho2017 and BNCI004 have no executable target contract. BNCI001 explicitly fails
the original 64-channel reference semantics. Complete future manifests require
new seals before any execution.

## Security and package receipts

The unchanged privacy checker inspects every current file, reachable historical
path/blob, commit/tag metadata, file size, binary payload and personal-home-path
pattern. Gitleaks 8.30.1 scans history, extracted blobs, the current tree and
metadata with default rules and inline allow comments disabled. The existing 65
exact-content reviewed false positives remain unchanged in each applicable scope;
metadata has zero findings. There are zero material secrets, restricted data
files or personal home paths. No reviewed exception was widened. Pattern scanning
and manual review cannot prove the absence of every possible disclosure.

Raw data, local outputs, environment files, credentials, private permission
records and model weights remain ignored. Distribution inspection rejects
restricted paths, identifiable binaries, private configuration and participant
outputs. Fixed-timestamp independent wheel/sdist builds are checked for byte
identity. Hashes and installation receipts stay in ignored local verification
storage; public evidence contains only reviewed aggregate facts and artifact
hashes. No human EEG is sent to CI.

## Remote publication gate

PR #9 was merged at `6229bf03a292399fff8041d2b6467d7f73dadebc`.
Its post-merge run 43008787792 retains 12 successful jobs and one comparison job
that never started because of GitHub billing/spending limits. This is an
infrastructure blocker, not a numerical test failure, and remains pending.

M25 retains all 13 required jobs and all eight prior synthetic comparison
families, adding external frozen validation as the ninth. The four actual runners
are Linux x86_64 / macOS arm64 with Python 3.11 and 3.12. Local execution cannot
establish those remote platform results. The PR and ignored completion receipt
record the actual M25 run/head/status. If any required job cannot execute, leave
the PR open and unmerged; do not remove, skip or replace its gate. Repository
visibility must remain private. No Milestone 26 execution is authorized by this
addendum.
