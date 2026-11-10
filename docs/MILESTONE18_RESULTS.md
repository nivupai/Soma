# Milestone 18 results addendum

Soma 0.18.0 adds opt-in typed workflow provenance, conservative dependency-aware
cache reuse, atomic publication/recovery and metadata-only graph inspection.
Baseline main was 9312c7c950ad915e989d8aefe2e8fd60ef7912d7. All 1,019 baseline
Python tests were rerun before implementation. Historical reports remain unchanged.

## Executed local verification

- Full suite: **1,090 passed**, 111 warnings; 71 workflow/adversarial tests added.
  Offline: **1,073 passed**, 17 integration tests deselected, 109 warnings.
- Frontend: **21 passed**. Configured local Playwright: **11 passed**, including
  node selection/keyboard navigation and assertions that every dependency edge
  renders. Demo-only CI retains the existing local-data browser skip.
- Ruff lint/format, strict mypy (219 source files), TypeScript, ESLint, Prettier,
  production frontend build, pip check and Python/npm dependency audits pass.
  No known dependency vulnerabilities; unpublished Soma has no PyPI audit record.
- Fresh noneditable wheel/sdist/source installations each run ten SDK examples
  from isolated working directories. Distribution inspection and repeated-build
  hashes are checked after the source tree is frozen.
- All 125 baseline test/experiment/frontend/browser files are byte-identical.
- Gitleaks 8.30.1 scans proposed files, full sanitized history, blobs and metadata:
  zero material secrets/restricted files/private home paths. Two existing findings
  and 63 generated workflow-cache SHA-256 findings are explicitly reviewed and
  bound to exact complete-file hashes. Every new finding matches an executed local
  cache receipt; see scanner-review.json. No scanner rule or data exclusion changed.
- Actual graph screenshots and numerical reports were inspected locally. New
  screenshots stay ignored; the six historically approved synthetic PNGs remain
  the only tracked binary exceptions.

The adversarial suite covers cycles, missing/duplicate dependencies, producer/type
mismatches, canonical type identity, omitted-parameter collisions, coordinate/unit/
ontology/policy guards, seed changes, corruption/missing/truncated metadata/arrays,
stale receipts/versions, path traversal/symlinks, keyed identities/redacted exports,
concurrent publishers, bounded memory and snapshotting external inputs.

Fault injection at seven execution/publication boundaries verifies that resumed
outputs match uninterrupted outputs under the same contracts. Partial writes/ENOSPC
never publish complete entries; after-publication interruptions reuse verified
results without trusting journal state. Corrupt published entries remain unchanged.

## Representative scientific outcomes

All four DAGs run cold, warm and after a scientific change, using existing Soma
methods. All 21 cold stages complete; all 21 warm stages are verified hits with
identical numerical content fingerprints. Ten stages are reused after the four
selected scientific changes; eleven dependent stages recompute.

| Workflow | Stages | Changed parameter | Reused on changed run |
|---|---:|---|---|
| EEG validation/reference/Welch/mu-beta | 5 | average reference to none | generation, validation |
| MRI geometry/N4/foreground/QC/surface | 6 | threshold 1.0 to 1.2 | generation, geometry, N4 |
| fMRI metadata/design/OLS/contrast/ROI | 6 | task weight 1 to 2 | BOLD generation/validation, design, fit |
| Toy geometry/forward/inverse/resolution | 4 | forward scale 1 to 1.2 | geometry |

EEG baseline channel mu powers are about 1.2305e-11 V² and beta powers 1.2505e-11 V².
MRI foreground volume is 4.416e-6 m³; this is a synthetic heuristic foreground,
not tissue/skull/scalp validation. The descriptive fMRI all-modeled-voxel effect
mean is -0.0259552 with mean variance 0.0658809. It does not test an anatomical ROI
or establish confirmation. Numeric OLS contrasts agree with Soma's full contrast
API at the fixed 1e-12 test bounds without refitting. Toy source estimate/resolution
diagonal is 1/1.1 for the identity forward; no anatomical localization claim.
All 12 Milestone 17 analytical/reference oracles are re-executed successfully.

## Performance observations

Local Darwin arm64/Python3.12 observations use three-repeat medians with tracemalloc.
For a branching graph with 1,000 stages/2,001 nodes: validation about 213 ms,
key computation 1.37 s, miss/resume planning 1.65 s, invalidation 847 ms and lineage
227 ms. Planning allocation peaks are below 6 MiB in these examples. The small
real source workflow took about 89 ms cold; verified warm execution/planning about
36 ms; Explorer metadata projection about 38 ms. Whole-process peak RSS about
299 MiB includes imported native libraries. Artifact reads can reserve about 64 MiB;
that is separate from small metadata-only graph projection. No timing gates or
universal performance guarantee; the machine-readable observations retain exact
values and scope. Scientific computation and graph overhead are distinguished.

## Scope, limitations and platform evidence

Logical, environment, cache/derivation, content and file-byte identities are distinct.
Exact-environment reuse is conservative; numerical agreement never authorizes
cross-platform cache interchange. Units/ontologies/inference policies cannot be
silently reinterpreted. All relevant algorithm parameters enter identity; separate
palette/layout preferences do not. Source-code changes conservatively invalidate
more broadly than parameter-only changes.

The graph layer reuses existing StageSpec ordering, pipeline value encoding and
staged publication patterns. Existing eleven-stage MRI/cohort engines and old
cache contracts are preserved; none is automatically upgraded to verified new hits.
This is a bounded serial extension, not a distributed scheduler or arbitrary-code
execution service. Registered custom SDK code is trusted operator code.

POSIX local same-filesystem rename/fsync and cooperating publishers are assumed;
Windows/network-filesystem guarantees are not claimed. Cancellation occurs at
stage boundaries, not inside native calls. Payload budgets exclude transient/native
allocations. Pseudonyms/redaction/hashes are not general medical deidentification
or authentication. Retain original access restrictions and keep private inputs,
outputs and local run records outside Git.

Configured Linux x86_64/macOS arm64 × Python3.11/3.12 jobs must execute before merge.
Actual platform comparisons and CI conclusions will be appended after inspecting
the downloaded synthetic-only artifacts; configuration is not evidence.

No new neural estimator, MRI tissue algorithm, fMRI confirmation model or clinical
readiness claim is introduced. Proposed Milestone 19: reviewed workflow protocol
versioning and controlled longitudinal replay. Milestone 19 has not been started.

## Executed first platform run and review corrections

[Run 42738321766](https://github.com/nivupai/Soma/actions/runs/42738321766) executed
all four actual replay jobs and their comparison on commit c5ff535. All four
workflows passed cold/warm/changed runs on each platform, alongside all 12 M17
oracles. The 12 cross-workflow-summary comparisons passed; maximum absolute
difference was 3.03e-14 (fMRI). This establishes agreement of selected summaries,
not equality of every intermediate voxel/array. Exact content and file identities
are recorded separately; numerical agreement does not permit cache interchange.

| Actual OS / architecture | Python | NumPy | SciPy |
|---|---|---|---|
| macOS / arm64 | 3.11.9 | 2.4.6 | 1.17.1 |
| macOS / arm64 | 3.12.10 | 2.5.4 | 1.18.1 |
| Linux / x86_64 | 3.11.18 | 2.4.6 | 1.17.1 |
| Linux / x86_64 | 3.12.16 | 2.5.4 | 1.18.1 |

The environment review then added pandas/scikit-learn/joblib/threadpoolctl versions,
OS/kernel/compiler builds, scientific installation-record digests and NumPy/SciPy
build-configuration digests. Local full tests remain 1,090 passing and all workflows
and M17 oracles pass with this stronger identity. Missing build evidence fails
closed. Installation/build records are not authentication of a hostile runtime.
The initial local verification JSON is immutable capture evidence, with its exact
SHA-bound scanner review; this addendum records subsequent identity hardening.

First-run Explorer CI exposed five accidental external ESLint lockfile edits made
during the Soma release-number update. They were restored to their original values;
Soma remains 0.18.0. A real clean npm ci, all 21 frontend tests, TypeScript, lint,
format, production build and dependency audit then passed. No test assertion was
weakened. Final-head CI must be entirely green before merge; the PR records its
actual workflow run and merge decision.
