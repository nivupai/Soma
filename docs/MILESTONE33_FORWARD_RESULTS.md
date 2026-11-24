# M33 forward-model revalidation (workstream D)

**Readiness label on every result: `QC_ONLY_ANATOMY`; skull not CT-validated.** These
are numerical forward-model results on the MNE sample conductor. They are not
anatomical, conductivity or source-localization validation, and a numerical pass never
upgrades the head's readiness.

Public aggregate: `experiments/milestone33/forward-revalidation.json` (aggregates only).
Runner: `scripts/run_forward_revalidation.py` (resumable; each stage in its own
subprocess, one at a time; private lead fields under the git-ignored `reports/`).
Helpers: `src/soma/source/forward_revalidation.py`. Tests:
`tests/source/test_forward_revalidation33.py`.

## Setup

- Conductor: MNE sample three-compartment BEM from the provided FLASH surfaces
  (brain/CSF homogenized), M32 conductivities 0.3 / 0.006 / 0.3 S/m.
- Sensors: 59 EEG channels, average reference (rank 58 at every level and solver).
- Sources: the M33 oct6 cortical midsurface source space (`soma.source.cortical`,
  7,618 sources), fixed orientation along the area-weighted outward normal. The 7,598
  sources inside the inner skull of every compared level are used throughout (20 lie
  outside the coarser level-3 inner skull; none are moved). Inner-skull margin to the
  level-4 surface: median 12.7 mm, 5th percentile 2.3 mm, minimum 0.05 mm.
- Free MNE head-frame coefficients are rotated to MRI and projected on the normals.
- Metric (identical to M32, `scripts/run_mri_head_models.py`):
  `||G_coarse − G_fine||_F / ||G_fine||_F` on average-referenced lead fields; solver
  agreement uses OpenMEEG as the reference. Target 10%.
- Margin strata (≥0, 1, 2, 5, 10 mm to the level-4 inner skull) were fixed in the runner
  before any lead field was computed.

## Levels

| Level | Inner skull / outer skull / scalp vertices | Note |
|---|---|---|
| 3 | 642 / 642 / 642 | MNE ico3 decimation (as M32) |
| 4 | 2562 / 2562 / 2562 | provided surfaces (as M32) |
| 5i | 10242 / 2562 / 2562 | level-4 geometry, inner skull midpoint-subdivided |

The provided surfaces are ico4, so a finer level cannot add geometry; 5i refines only
the boundary-element discretization of the inner skull, the surface nearest the
sources. **Full level 5 was not run (infeasible here):** 30,726 MNE unknowns need about
7.5 GB per dense matrix copy (and OpenMEEG more) on a 16 GB machine. OpenMEEG at 5i
(~41k unknowns) was not run for the same reason. The 3→4 step changes geometry and
discretization; 4→5i changes discretization only.

## Mesh refinement (MNE BEM)

| Pair | All 7,598 | ≥1 mm (7,525) | ≥2 mm (7,310) | ≥5 mm (6,391) | ≥10 mm (4,718) |
|---|---:|---:|---:|---:|---:|
| 3→4 | **36.87% FAIL** | 20.59% | 12.90% | 6.97% | 6.27% |
| 4→5i | **21.48% FAIL** | **6.94%** | 2.09% | 0.24% | 0.16% |

Per-source relative error, 3→4: median 6.50%, 95th 33.95%, 99th 100.3%.
4→5i: median 0.17%, 95th 7.02%, 99th 43.9%. The global failure is concentrated in the
few sources within 1–2 mm of the inner skull (shorter than the ~5 mm level-4 edge),
where the BEM potential is nearly singular; away from the skull level 4 is converged
to well under 1%.

**Decision.** With the unrestricted source space the change between the two finest
levels (4→5i, 21.48%) fails the 10% target, so **no minimum mesh level is established
for sources closer than 1 mm to the inner skull**. With a ≥1 mm source margin (99.0%
of sources retained) 4→5i passes at 6.94% while 3→4 fails (20.59%): **minimum human
mesh level = 4**, conditional on that margin (`minimum_human_mesh_level_by_source_margin`
in the JSON). Level 3 is adequate only for sources ≥5 mm from the skull. Applying a
1 mm margin is a source-space policy choice for downstream use; it is not applied
silently here and only one passing pair (4→5i) supports the level-4 choice.

Compared with M32 (140 volumetric sources ≥9.9 mm from the skull, free orientation:
2→3 14.56%, 3→4 5.12%), the cortical result at ≥10 mm (3→4 6.27%) is consistent; the
new failures come from cortex the volumetric space never sampled.

## MNE-BEM vs OpenMEEG (same surfaces, same sources)

| Level | All sources | ≥1 mm | ≥2 mm | ≥5 mm | Per-source rel. error p50 / p95 / p99 | Correlation p5 / p50 |
|---|---:|---:|---:|---:|---|---|
| 3 | 32.92% | 21.28% | 14.23% | 9.15% | 8.59% / 33.7% / 99.5% | 0.9786 / 0.9993 |
| 4 | 25.43% | 7.53% | 3.38% | 2.56% | 2.38% / 7.94% / 50.0% | 0.9991 / 0.9999 |

Disagreement shrinks with refinement and with source margin, consistent with both
solvers converging away from the boundary; near-skull sources dominate the global
figure. M32 reported 6.81% at level 3 with deep volumetric sources. These are matched
numerical differences, not ground-truth solver error.

## Runtimes and memory (one process at a time)

| Stage | BEM unknowns | BEM solve | Total | Peak RSS |
|---|---:|---:|---:|---:|
| MNE 3 | 1,926 | 2.3 s | 7.2 s | 388 MiB |
| MNE 4 | 7,686 | 33.9 s | 53.1 s | 1,979 MiB |
| MNE 5i | 15,366 | 251.1 s | 289.2 s | 5,338 MiB |
| OpenMEEG 3 | 1,926 | 14.1 s | 34.3 s | 668 MiB |
| OpenMEEG 4 | 7,686 | 625.2 s | 695.4 s | 4,205 MiB |

Source-space build 12 s and geometry checks 45 s. Lead fields are computed in chunks of
1,000 sources. Lead nonnull condition numbers 115–159 (fixed orientation).

## Limitations

- One conductor (MNE sample), QC_ONLY anatomy, skull not CT-validated, literature
  conductivities, no independent full-conductor reference.
- The finest level refines the inner skull only; outer skull and scalp stay at ico4.
- The level-4 choice rests on a single passing pair and a 1 mm source-margin policy.
- EEG only; MEG was not revalidated here.
