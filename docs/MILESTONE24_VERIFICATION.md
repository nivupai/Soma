# Milestone 24 verification addendum

This addendum records v0.24.0 without rewriting prior milestone reports.

| Gate | Inspected local evidence |
|---|---|
| Full cached Python suite |1,453 passed; all1,420 baseline tests plus33 additions;117 warnings |
| Offline archive suite |33 passed with network sockets forbidden |
| Preserved scientific/test baseline |285 protected file hashes checked before publication |
| Ruff / formatting / strict mypy | Pass;271 typed source files |
| Frontend unit tests |36 passed; all34 originals preserved |
| Playwright |17 passed; all16 originals preserved; installed wheel API |
| TypeScript / ESLint / Prettier / production build | Pass; existing Vite large-chunk advisory remains |
| Actual source fit |35 subjects,105 recordings,1,441 retained trials; five complete new private capsules |
| Training-session reload | Exact labels/decision scores and supported probabilities for all1,441 trials/model |
| Independent reload | Two authoritative restarted processes, separate working directory, noneditable wheel, exact dependency snapshot, all supported fit methods disabled |
| Ordinary newly resolved environment | Correctly BLOCKED for version/installation-identity differences; not silently accepted |
| Numerical tolerances | Prespecified rtol1e-9/atol1e-9; actual maximum error0 in supported outputs |
| Source-fold historical comparison | M22 fixed-setting source means agree within1.12e-16; no historical target-role reevaluation |
| Requirements / dependency audits | No broken requirements or known third-party/npm vulnerabilities; unpublished Soma excluded from PyPI lookup |
| Package acceptance | Final wheel/sdist/source receipts and reproducible-build hashes recorded locally before publication |
| Privacy / Gitleaks8.30.1 | Zero material secrets, restricted files or personal home paths; same65 exact reviewed false positives; no widened exceptions |

The standard fresh wheel installation is distinct from the exact-reproduction
installation. The latter faithfully snapshots the training dependencies, excludes
Soma/services source and editable hooks, and installs a wheel noneditably. No model
object or cached training state is copied into it. Existing M23 environment/source
checks remain unchanged. It demonstrates this preserved environment, not arbitrary
cross-environment model portability or scientific cache interchange.

The final guarded restart receipts disable sklearn pipelines/scalers, LR/LDA,
MNE CSP, trial covariance/OAS/LedoitWolf, MDM and tangent fit methods. They read only
bounded native numeric artifacts and authorized probe inputs. The normally resolved
environment failure and duplicate-write refusal are retained as failed attempts;
neither is relabeled success or used to alter the release.

The two aggregate figures and actual Explorer capture were visually inspected.
Only reviewed source-fold summaries, protocol/release identities and metadata-only
acquisition/readiness evidence enter Git. Real coefficients, projection filters,
covariance means, probes, participant distributions and trial predictions remain
ignored and private. Model parameters are potentially sensitive derivatives;
redistribution has not been authorized. No scanner exception was added.

GitHub retains13 jobs and adds an eighth synthetic comparison family. Before merge,
inspect all13 jobs on the exact feature SHA and download all four actual macOS
arm64/Linux x86_64 Python3.11/3.12 artifact bundles. Repeat on the exact post-merge
push run, then verify private visibility and clean synchronized local/remote main.
The PR and completion report link the observed runs; local synthetic checks do not
substitute for remote evidence. CI receives no human EEG or real fitted weights.

Detailed logs, private model/probe manifests, native verification, dependency snapshot
records, package checks and downloaded CI bundles remain in ignored local reports.
Public file hashes are in `experiments/milestone24/evidence.json`. External acquisition
and human evaluation remain BLOCKED. No Milestone25 work was started.
