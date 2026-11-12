# Milestone 27 — measured nonspherical BEM results

Version 0.27.0 extends the existing source uncertainty workbench with a frozen
synthetic four-interface BEM experiment. Baseline main was
`fa6a0fc765692271954f48d694880efc372e8ebb`; all historical M26 numerical artifacts
remain unchanged. The design was committed at `3687ced`; revision 2 at `ecc595f`
retains the original and documents a pre-outcome geometric margin amendment.
Local seals do not establish external preregistration.

## Actual findings

- Six independently seeded heads: two prolate, two oblate, two smoothly asymmetric.
- Four closed nested interfaces at 20/80/320 estimated triangles/interface;
  a distinct 1280-triangle reference; 72 independent off-grid source draws.
- 32 sensors; 1224 shared measurements; 44,064 computed reconstruction rows;
  no reconstruction failures or omitted planned heads/configurations.
- Minimum tissue separation 1.111 mm; triangle quality ≥.95354; aspect ≤1.36467;
  no detected intersections, manifold or orientation failures in executed models.
- Exact homogeneous spherical error falls to .7905%; four-shell MNE
  semi-analytical reference difference to .9601% at finest resolution.
- All six nonspherical whole-model mesh studies pass frozen convergence criteria;
  L2 relative field differences are 2.181–2.280% versus the finer reference.
- All six independent matched THREE-layer controls **fail** the 10% agreement
  target, with 16.088–17.610% differences. Full four-layer independent numerical
  validation remains **NOT_ESTABLISHED**; passing limiting/convergence references
  does not override this disagreement.
- L2 peak localization at .05 µV: Tikhonov **20.795 mm**, MNE **20.929 mm**,
  dSPM **20.999 mm**. Coarse-mesh errors rise markedly; modest perturbation
  effects are small compared with the fixed inverse-grid limitation.
- Maximum discrete-system residual 3.24e-14, primary study 349.041 s,
  maximum solver-child peak RSS 1135.84 MiB. No FEM PDE residual is claimed.
- **FEM_NOT_PERFORMED; PHANTOM_NOT_AVAILABLE; zero human subjects.**

[Mesh checks](HEAD_MESH_VALIDATION.md), [reference hierarchy](BEM_FEM_REFERENCE_COMPARISON.md),
[convergence](HEAD_MODEL_CONVERGENCE.md) and
[conditional source uncertainty](NONSPHERICAL_SOURCE_UNCERTAINTY.md) give the
interpretation and exact scope. Complete per-source/per-head/aggregate tables,
paired intervals, forward and measurement tables, resolution diagnostics,
M17 native result envelope, M19 seal, hashes, geometry fingerprints and ten SVG
figures are in `experiments/milestone27`. Public values are exclusively synthetic.
Figures were rendered and visually inspected; display meshes are labeled examples.

## Audit and limitations

The final executed solver worker and experiment source snapshots are archived
under `implementation`, byte-matched to their recorded hashes. The earlier
spherical-reference worker is retained separately. A first complete run omitted
explicit synthetic-only envelope metadata; the strict new reader correctly
rejected it. The producer was fixed and the complete unchanged experiment repeated.
All **40 numerical CSV tables (including 44,064 reconstruction rows)** are
byte-identical across runs, as are all six convergence and six independent-control
results. The first run and unsuccessful adapter attempts remain locally retained;
`repeat-verification.json` records the comparison. No physical settings, thresholds
or regularization were tuned. The final native envelope passes direct read-back.
Analysis postprocessing uses recorded matrices and the unchanged inverse/Resolution
APIs. Hashes establish content identity, not external preregistration timing.

The spherical control differs in shape, sensor mapping and formulation, so the
observed field difference is not a pure isolated shape effect. Coarse scalp
projection reaches 19.493 mm and contributes materially to whole-model convergence.
The six heads and two heads/family do not characterize human anatomical variation.
No conductivity anisotropy, real electrode errors, human skull segmentation,
participant accuracy or measured source ground truth is established.

Proposed Milestone 28: investigate the unresolved matched three-layer discrepancy
with a separately frozen refinement/independent reference design, then establish
an authorized four-layer physical reference or documented phantom validation.
Milestone 28 has not begun.

## M26 baseline audit retained

M26 modeled one four-shell sphere with twelve off-grid generators and 204 shared
measurement vectors. Its 49 configuration rows represented 45 distinct physical
settings. It computed 24,480 reconstructions, with 5508 failed rows and nine
rejected configurations; the reported baseline dSPM error at .05 µV was 18.657 mm.
A finer inverse grid materially reduced its error. Independent physical forward
verification was not established. These remain historical conditional findings,
not human anatomy accuracy or directly matched six-head M27 estimates. This
milestone preserves those original protocols, measurements, tables and figures.
