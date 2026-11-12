# Milestone 27 verification addendum

Baseline main was `fa6a0fc765692271954f48d694880efc372e8ebb`, PUBLIC nivupai/Soma,
with 1521 Python tests, 40 frontend tests, 19 browser tests, 18 SDK examples in
three isolated installations and verified 13/13 PR/postmerge jobs. The nine
previous cross-platform families and immutable archive were audited before work.
The design and explicit pre-outcome amendment are separate commits; M26 reports
and measurements are unchanged. This document adds M27 evidence rather than
rewriting historical reports.

## Local verification

The complete suite has 1559 tests (38 new), including 17 explicitly cached local
integration cases. The offline selection has 1542 tests. Scientific assertions
and all pre-existing tests remain unchanged. The prior 354 protected baseline
files, 41 M26 immutable numerical/protocol/document files, earlier 317 historical
files and 46 M24 archive files are checked by SHA256. No medical data is exported.

Frontend verification covers 42 tests, TypeScript, ESLint, Prettier, production
build and npm audit. There are 20 browser tests with explicit local allowlist;
the demo-only CI configuration intentionally skips the pre-existing local-file
case. The initial browser attempt reused a stale v0.26 backend and failed the
new endpoint check; restarting the verified workspace server resolved that issue.
The synthetic-only attempt passed 19 with the existing local case skipped; the
full configured repeat exercises all 20. No assertion was relaxed.

Ruff, formatting and strict mypy cover all source/services. Dependency consistency
and vulnerability audits include the optional pinned OpenMEEG solver. The project
itself has no auditable PyPI record; this is recorded separately from dependency
findings. Vite reports the existing source chunk-size advisory; the build passes.
Three fresh noneditable wheel/sdist/source installations test core and Explorer,
all 19 SDK examples and installed payload equality against the reproducible wheel.
Two fixed-timestamp builds must produce identical wheel and sdist bytes. Distribution
payload inspection rejects private medical binaries, credentials and home paths.
Hashes and actual command receipts belong to the public verification JSON.

The scientific run has 44064 computed rows, no failed reconstructions, six failed
independent three-layer agreement gates and explicit unsupported four-layer/FEM/
phantom claims. All ten SVG figures were rendered and visually inspected; field,
measurement and source identities, paired estimates, conditional intervals,
mesh/solver diagnostics and native result envelopes were inspected directly.
Additional postprocessing derives linear PSFs and paired contrasts from recorded
forwards. The final executed worker/experiment snapshots match their recorded hashes. A first run omitted explicit synthetic-only metadata and was rejected by the new reader. The producer was corrected and the entire unchanged frozen experiment repeated, with every numerical table compared against the retained first run; no physical settings or thresholds were tuned.

Privacy/history scans use the unchanged checker and Gitleaks 8.30.1. Existing
exact-content false-positive reviews remain unchanged: no broad suppression or
new licensed/human artifacts are introduced. Raw data, local results, .env files,
credentials and unreviewed weights remain ignored. A clean scan is pattern-based
evidence, not a proof that every possible secret can be detected.

## Remote gates

The existing 13-job workflow and four-runner matrix remain required. Small
analytic BEM cases add a tenth comparison family; the expensive six-head study
is not run in ordinary CI. All nine historical comparisons remain unchanged.
Require successful PR checks at the intended head before merging, then separately
verify postmerge CI, download four actual platform bundles and rerun all ten
comparisons. Confirm matching local/remote main, a clean tree and PUBLIC visibility.
The PR and final completion receipt record actual run URLs, head and merge hashes;
local results alone do not establish remote success. No force push or visibility
change is authorized or used. Milestone 28 has not started.
