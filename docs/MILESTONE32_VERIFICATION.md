# M32 verification addendum

## Integration and frozen evidence

M31 reviewed head db33aa0c3f01475878b87e8484a7980d10de5470 was already merged at
3aff2339a6d8133815eb1cd9a4fb1d8e134587f8. Post-merge run
[44694634385](https://github.com/nivupai/Soma/actions/runs/44694634385) passes all
14 jobs. Its native Gmsh diagnostic retains scientific FAIL and policy-satisfied status.
Local main was synchronized and clean before the M32 branch was created.

M32 protocol/seal commit d2bbe03 precedes final human processing. Design SHA256:
89690086412e8682d4f4d19e7657644588b7e240590f15afd2dd464c3cf5d619.
Historical tissue outcomes were known; local sealing is not external preregistration.
Six executed scientific-code hashes match implementation commit dd7d6b6. Exact-code
replay reproduces every scientific metric and all four lead-field CSVs byte-for-byte.
Scalar execution provenance contains code/config hashes and software versions only.
No raw-image-derived fingerprint, private path or participant geometry is public.

## Local verification

- Complete Python suite: **1,770 passed**, including all 1,725 historical tests and
  45 new analytical, evidence, numerical and privacy regressions; 117 warnings.
- Final offline suite: **1,753 passed, 17 integration tests deselected**, 115 warnings.
  The complete run above includes those 17 cached-data integration tests.
- Ruff and formatting: pass, 743 Python files. Strict mypy: **299 files**, no issues.
- Final frontend: **52 unit tests pass**; TypeScript, ESLint, Prettier and production
  build pass. Existing large-chunk advisory remains a nonblocking build warning.
- Final configured browser suite: **26 pass**, including actual local MRI/overlay and
  conductor access. Ordinary public CI omits only the two explicit local-data tests;
  it neither downloads participant anatomy nor substitutes a synthetic human image.
- Disabled-by-default private routes require explicit opt-in, direct loopback client
  and loopback host/origin; forwarded requests are denied. Both new mesh and existing
  M32 MRI metadata/slice paths are guarded. Synthetic adversarial access tests pass.
- Metadata audit rejects substituted MRBrainS test paths before opening headers;
  this was separately exercised with a synthetic inventory and an I/O-failing mock.
- **24 SDK examples pass**. Fresh noneditable wheel, sdist and source installations
  each pass all 24 examples, dependency consistency/audit and **326 payload comparisons**.
  Isolated installed physical BEM/FEM/Gmsh smoke checks pass. No system-site-package or
  source-checkout import is used to satisfy those installed checks.
- Independent fixed-epoch wheel/sdist builds have identical bytes. Distribution
  members are inspected for medical files, private paths, credentials and large artifacts.
- Full `npm ci` and repeated full npm audits: **zero vulnerabilities**. No audit ignores,
  omitted development dependencies or weaker CI thresholds. Python dependency check
  and audit pass; unpublished local Soma itself is not a PyPI-auditable dependency.
  Fresh environments upgrade bootstrap pip to 26.3 before their security audit.
- Public-safe tree/history scan uses Gitleaks 8.30.1 plus path, binary, size, metadata
  and reachable-object checks. No material secrets, restricted medical files or personal
  home paths are found. Existing content-bound reviewed false positives are preserved;
  no new suppression or exception is introduced. A final publication scan retains its
  full receipt under ignored local reports and is repeated by mandatory CI security.
- Raw/external/anatomy/derived data, local reports/derivatives, .env and credentials
  remain ignored. All **1,054** pre-M32 experiment/configuration/test hashes and all
  **46 M24 archive files** are unchanged. Historical reports are not edited.

Warnings include explicit IBSR units conventions, coded MRBrainS qform/sform disagreement
within its frozen .5 mm bound, existing fMRI masking notices and third-party TestClient
deprecation. None is used to hide a failed gate. All original numerical tolerances and
release-policy files are preserved.

## Numerical and publication gates

The actual human study retains 23 failed tissue-target cases and a failed 14.56% coarse
refinement target. Primary fine refinement 5.12% and matched BEM 6.81% meet their frozen
10% engineering targets. Successful execution is not full-head anatomical validation.
The initial export-field implementation error, missing independent conductor truth,
limited source coverage and unavailable BEM algebraic residual remain explicit.

The four-platform CI adds a small independently checked synthetic MRI-frame and
irregular voxel-prior fixture (elementwise rtol 1e-10, atol 1e-12). This tests software
portability only: restricted human lead fields are **not** independently replicated in
public CI. Malformed, missing or mismatched reports block its gate. Existing M31 and
all older comparison families remain mandatory.

The original M30 canonical-mesh comparator remains mandatory at rtol .02/atol .01.
The original native comparator, failure entries and characterized-failure release
policy remain unchanged. Native scientific FAIL is expected, not relabeled PASS;
invalid reports or a changed failure signature still block release.

Publication-time exact-head results, run URL and downloaded four-environment comparisons
are recorded in the M32 pull request and its Actions artifacts, associated with the
actual published commit. Consult the [branch workflow runs](https://github.com/nivupai/Soma/actions/workflows/ci.yml?query=branch%3Afeature%2Fmilestone32-mri-head-models)
and PR checks rather than inferring cross-platform success from a local run. All 14
jobs must pass before scientific review. Stop at the PR; **no M32 merge or M33 work**.
