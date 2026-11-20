# Milestone 31 verification

Base: M30 merge `4e55256f8dcbcb9a104e4b7b16ad495cdabc9191`, main synchronized
before branching. Feature: `feature/milestone31-inverse-calibration`, v0.31.0.
Protocol commit: `44adeed`; design SHA256:
`abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc`.

Baseline collected 1,699 tests and 22 SDK examples. One initial cache-ID assertion
failed while development changed the working-tree provenance during that run;
the unchanged assertion passed when rerun with a stable tree. Final full/offline
verification is performed on a stable committed implementation. Earlier tests and
numerical assertions are preserved. All 957 previously tracked experiment/config/
test files are hash-checked, plus the 46 separately archived M24 model files.

New coverage includes analytical coefficient-space normal equations, exact MNE
trace/global-scale cancellation, positive covariance/mass/units/ordering, immutable
inputs, invalid positions, whitening, selection/split guards, inappropriate dSPM
physical amplitude, clustered uncertainty shape, corruption/missing failures,
read-only API, cross-grid resolution rejection and four-platform reference checks.

The full scientific experiment is excluded from ordinary CI. A small fixed
inverse-prior reference and numerical comparison are added to all four actual
platform runs without changing the canonical-mesh gate or native release policy.
M30 post-merge CI run 44626578312 already fails native signature classification;
canonical passes. The new scientific PR must remain open if that required condition
continues to fail. There is no audit exception, error ignore or relaxed tolerance.

Scientific execution: all 3,726 configurations and 99,360 rows computed, zero
numerical failures. Independent replay agrees on every reconstruction numeric
entry (rtol 1e-10, atol 1e-12), with all six fresh truth fields byte-identical.
Initial resource use: 33.372 s, process peak 775.406 MiB; replay: 31.823 s,
852.828 MiB. These include imports, fresh truth solves and table writes; per-kernel
cost and cumulative RSS are separately labeled. The twelve figures were visually
inspected. Gmsh portability and MRI-derived anatomical accuracy are not established.

Final test, security, packaging and exact-head GitHub receipts are recorded in a
verification addendum after checks complete. No merge or M32 is authorized by
passing this local study alone.

## Final local numerical checks

Full suite: 1,725 passed (117 warnings); offline suite: 1,708 passed, 17 integration
tests deselected (115 warnings). All earlier 1,699 tests remain present. There are
26 new Python regressions, 50 frontend tests and 24 configured local browser tests.
Ruff/formatting, TypeScript/lint/Prettier and strict mypy over 295 source files pass.
SDK examples increase from 22 to 23. Complete npm audit reports zero vulnerabilities;
Python dependency consistency/audit pass (the local Soma package is not on PyPI
and is reported as unauditable by pip-audit). No audit ignore was introduced.

The new cross-platform fixture uses exact analytical Voronoi slab volumes for
three collinear sites, avoiding platform-sensitive quadrature inputs when testing
inverse arithmetic. A separate analytical integral check bounds the fixed Sobol
fixture's absolute cell-mass fraction error by 5×10⁻⁴; this is an additional bounded
geometry regression, not a relaxation of M30 or algebraic tolerances. The full
scientific experiment continues to use its originally frozen Sobol quadrature.
