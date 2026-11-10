# Milestone 19 results — Soma 0.19.0

This is a new report. Historical scientific reports and frozen configurations are
unchanged. The audited baseline was main `b54e400fd06fbeafe934da3bc1b9eabe77dab405`:
1,090 Python tests, 21 frontend tests and 11 local browser tests. Work is confined
to the sanitized checkout and the existing private repository.

## Implemented evidence

Strict finite schemas `soma.protocol/1.0.0`, `soma.protocol.seal/1.0.0` and
`soma.protocol.execution/1.0.0` separate scientific declarations from execution,
input, environment and cache identities. Existing result schemas 1.0.0/1.1.0,
scientific estimators and M18 exact-environment caching are preserved. Local seals
are deterministic and immutable through supported APIs; they prove neither
independent preregistration nor timing/authorship. Editorial compatibility is
structurally checked; scientific changes require explicit major amendments.

Eight historical protocol systems were inspected. The new inventory records
actual configuration/document/receipt hashes and which recorded hashes match.
The EEG initial receipt binds `configs/decoding.yaml`; the separate development
selection artifact `decoding-frozen.yaml` is inventoried with its own observed hash,
not incorrectly checked against the initial receipt. Historical receipt formats
differ; unsupported complete study/execution bindings
and independent registration evidence remain INDETERMINATE. No historic study is
silently converted to a new prospective or confirmatory protocol.

EXACT, CONTROLLED and EXPLORATORY modes delegate to registered M18 operations.
All prespecified units are retained. Unsupported overrides, arbitrary operations,
trial-level participant units, selective missingness and confirmation requests are
rejected. Seven drift categories distinguish data, protocol, implementation,
environment, numerical, outcome and missing evidence. Missing input evidence is
not itself proof that input content changed.

## Observed synthetic histories

| Family | Records | Sampling units | Controlled change | Exploratory amendment |
| --- | ---: | --- | --- | --- |
| EEG | 4 | 2 → 3 independent seeded realizations | Expanded cohort, same eligibility | Reference average → none |
| MRI | 4 | One realization per execution | Explicit new snapshot/session | Threshold 1 → 1.2 |
| fMRI | 4 | One synthetic BOLD realization per execution | New snapshot/session; actual platform comparisons in CI | SPM/OLS → Glover/AR1 |
| Source | 5 | One dimensionless toy per execution | New declared snapshot/session; actual platform comparisons in CI | Regularization 0.1 → 0.2; unsupported physical conductivity blocked |

There are 17 execution records, 22 scheduled unit observations, 21 completed and
one blocked. These are computational histories, not repeated human measurements.
Same-unit new sessions are deliberately not pooled or numerically aligned as if
session input data were identical. No aligned evidence is reported explicitly.

All four exact repeats recomputed in separate empty caches: output-file bytes,
selected numbers and frozen numerical equivalence agreed locally. New data were
classified CONTROLLED_DATA_CHANGE; scientific method amendments were
EXPLORATORY_DESCRIPTIVE; submitting those methods as CONTROLLED was REJECTED.
Conductivity was INDETERMINATE because the toy forward model has no physical
conductivity support. No surrogate conductivity effect was invented.

MRI intensity predictions were scored against an independent analytic radius-5
foreground reference used only for scoring: Dice/Jaccard 1.0, ASSD/HD95 0 mm in
this high-separation synthetic baseline. This is one binary foreground example,
not validation of brain tissue segmentation, skull/scalp conductors or human
anatomical accuracy. Method changes produced observed selected-summary differences;
those differences do not establish biological drift or statistical significance.

Machine-readable local evidence is in `experiments/milestone19/replay-summary.json`
and `performance.json`. Full execution/cache artifacts and inspected figures remain
in ignored local output directories. The public synthetic summary omits embedded
raw execution journals, which contain cache identifiers. No medical arrays or
participant artifacts are committed.

## Local verification

- Full suite: 1,161 passed (1,090 preserved + 71 new); 117 dependency/model warnings.
- Frontend: 24 passed (21 preserved + 3 new); TypeScript, ESLint, Prettier and build pass.
- Browser: 12 passed (11 preserved + 1 new) against a fresh noneditable wheel
  backend launched outside the checkout.
- Ruff, formatting, strict mypy (228 source files), pip check and dependency audits pass.
- Gitleaks 8.30.1 scans current tree and all reachable sanitized history: zero
  material secrets/restricted data/private home paths; 65 existing exact-file
  reviewed false positives, no rule suppression or new exception.
- 217 baseline test/configuration/experiment files retain their original hashes.
- Final wheel/sdist/source isolated noneditable installations and all 11 SDK
  examples passed in each environment. Two independent fixed-epoch builds produced
  byte-identical wheel and sdist files. Distribution member/privacy inspection passed.

Performance is observational, with no machine-specific CI timing gate. On local
macOS arm64, four/100-stage protocol validation was approximately 0.6/11 ms, sealing
0.9/16 ms, structural comparison 1.6/80 ms, conformance 22/33 ms and planning
111/245 ms. Two-record history queries were 224 ms, drift classification 121 ms,
and Explorer comparison 245 ms. These are three-repeat medians of metadata work,
separate from approximately 23 seconds for all scientific demonstrations. Exact
observations, environment and timings are in the machine-readable table.

## Cross-platform and publication verification addendum

Actual PR run [42767440824](https://github.com/nivupai/Soma/actions/runs/42767440824)
executed macOS arm64 and Linux x86_64 with Python 3.11/3.12 at source commit
`0cdc29436dce23e50871fbc0740739bb55b66339`. All 13 jobs passed, including all four runner jobs. Downloaded
artifacts were independently compared locally, and source fingerprints were checked
against that exact Git tree. All four protocol identities and workflow semantics
matched. All 20 selected unit-vector comparisons met the original frozen bounds:
five baseline self-comparisons and 15 comparisons across different environments.
Eleven were numerically identical; nine required tolerance-based agreement. File
bytes and input content identities are reported separately in
`experiments/milestone19/platform-comparison.json`; differing bytes do not imply
failed numerical validation or permit cache interchange.

This evidence validates the scientific protocol demonstrations at the named commit.
A subsequent conformance guard rejects falsely relabeled physical units and requires
runner implementation fingerprints to match the comparison checkout. It changes no
scientific algorithms, parameters or tolerances. The final PR head must pass the
entire 13-job matrix before merge. PR: [#4](https://github.com/nivupai/Soma/pull/4).
Final merge/main identity is reported in the completion receipt after successful CI.

## Scientific limitations

Executable eligibility/session adapters are synthetic only. Human identity, task
correspondence, access permission and longitudinal reliability are unimplemented.
Historical metadata remain partial. Local hashes are not authenticated provenance.
Summary agreement is not full-array or study equivalence and never authorizes
cross-environment cache interchange. No tolerance was widened. Human/feasible-AR
fMRI confirmation restrictions remain unchanged. Synthetic MRI/source success does
not close human tissue, conductor, coregistration or anatomical-readiness gaps.

A possible Milestone 20 is externally attested protocol registration and reviewed
real-data identity/session adapters with explicit permissions and task matching.
Milestone 20 has not been started.
