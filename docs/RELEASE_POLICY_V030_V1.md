# Soma v0.30.0 release policy v1

Policy ID: `soma-v0.30.0-release-policy-v1`, version 1.0.0.
Decision authority: explicit user instruction dated 2026-11-19.
Machine-readable policy: `configs/release-policy-v030-v1.json`.

This is a prospective software release-policy change. It does not amend, reseal,
recompute, retrospectively pass or replace the historical failed M30 scientific
protocol. Original measurements, failure tables, seals, hashes and the frozen
native comparator remain unchanged. No Milestone 31 work is authorized.

## Mandatory release guarantee

Canonical-mesh v1 numerical reproducibility is mandatory on all four actual
Linux x86_64/macOS arm64 Python 3.11/3.12 CI environments. It uses an identical
serialized, fingerprint-verified synthetic mesh and the existing FEM calculation.
Its unchanged mandatory comparison invokes the frozen strict comparator on all 192
field entries with rtol 0.02 and atol 0.01 V/(A m). Any malformed canonical report,
missing environment, physical-input mismatch or elementwise violation fails CI.

Every existing scientific test, other numerical comparison, frontend/browser test,
security audit, package verification, dependency check and privacy check remains
mandatory. No `continue-on-error`, audit exclusion, weakened tolerance, shell error
ignore or skipped scientific/security check implements this decision.

## Native diagnostic: scientific FAIL, conditional nonblocking finding

Native Gmsh cross-platform portability remains unestablished. The original native
comparator and its frozen tolerances execute in CI. Its original scientific result
remains **FAIL**. Only the previously characterized numerical field disagreement
may be reported without failing the aggregate release workflow.

The mandatory policy handler validates every primary report and companion before
calling the frozen comparator, which can otherwise stop at an early mismatch.
Validation includes four distinct environments, schemas/protocol/fixture identity,
complete controls, unique JSON keys, finite numeric values, units/reference/source order, source/sensor
identity checked against frozen geometry with native roundoff bounds, positive tetrahedra, material labels,
interface facets, physical volumes/quality, mesh fingerprints, solver residuals,
CSR/RHS structure, numerical options, and independent consistency of the reported
homogeneous reference error. An absent or malformed companion is blocking too.

After validation, the handler executes the original comparator. It recognizes
only its exact field-disagreement exception. Every other exception remains a
blocking error. The known case must then match all six pairwise comparisons:
all failed sensor/column indices and all 192 signed discrepancy components.
The pinned characterization is `configs/native-mesh-disagreement-v1.json`, derived
from already archived failed reports, whose byte hashes are verified as well.

Characterization replay uses rtol 1e-10 and atol 1e-9 V/(A m) on the *discrepancy
vectors*, solely to identify the previously observed failure despite insignificant
roundoff. These are additional, much tighter classification checks. They do not
replace or relax the original scientific field tolerances. No per-platform expected
lead field is used as an accuracy reference or as the release guarantee. An
aggregate error or unchanged failure count alone cannot satisfy this classification.

The allowed output always says `scientific_status: FAIL`, `all_passed: false`,
`original_M30_gate: FAIL_PRESERVED`, and `native_portability_established: false`.
Its separate release disposition is
`NONBLOCKING_CHARACTERIZED_SCIENTIFIC_FAILURE`. A successful reporting step means
that this prospective policy was satisfied, not that native meshing passed.
The scientific failure appears explicitly in the CI step name, console, job
summary and uploaded machine-readable diagnostic.

Missing, incomplete, invalid or unsupported reports; any failed control or new
physical/numerical problem; a different discrepancy vector or failing-entry pattern;
or an unexpected native scientific pass all block CI and require review. A future
native improvement cannot silently erase the original failure: it needs a separately
reviewed characterization/policy revision. Invalid executions write a blocking
status artifact and exit nonzero. Artifacts are uploaded even when validation fails;
that upload does not override the failed check.

## Rationale and limits

The native runs construct different interior meshes even with identical boundary
inputs. On a common serialized mesh, FEM fields agree near 1e-14 relative across
platforms. Source inspection and runtime probes identify nonportable random streams
and native geometric operations as plausible contributors, without proving one
exclusive upstream cause. Fixed-mesh numerical portability is an appropriate bounded
software guarantee; deterministic native mesh generation is not established.

Canonical v1 is a post-outcome homogeneous synthetic control, not evidence of
four-tissue anatomical accuracy, human validation, phantom accuracy or deterministic
native preprocessing. The full M30 study and its negative findings remain intact.
The old canonical study's `NOT_AUTHORIZED` release-decision metadata is preserved:
that experiment cannot itself authorize policy changes or a merge. This separate
user-authorized policy governs release acceptance prospectively; it does not confer
merge approval.

## Review and merge boundary

The release-policy and signature bytes are pinned by SHA256. Changes require an
explicit versioned review. Regression tests verify that the original scientific
failure cannot disappear or be relabeled as a pass, that invalid late reports
cannot hide behind an earlier known disagreement, and that canonical/security
checks remain mandatory.

All required CI jobs must pass under this documented policy, canonical numerical
reproducibility must pass, native scientific FAIL must be honestly reported, all
historical artifacts must retain their hashes, and the PR diff must be reviewed.
The current task explicitly stops before merging PR #15. No automatic merge, branch
protection change, release publication or Milestone 31 work is authorized.
