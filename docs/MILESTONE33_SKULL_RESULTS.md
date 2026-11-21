# M33 skull results: T1-only baseline vs CT bone (SynthRAD2023 brain)

Protocol: `docs/MILESTONE33_SKULL_PROTOCOL.md`, sealed by the project owner in
`configs/m33-skull-freeze.json` before any scoring. Aggregates only (CC BY-NC 4.0):
`experiments/milestone33/skull-aggregate.json`. Per-case outputs stay local.

> **Correction (2026-11-21): these v1 results are not reliable.** An audit after scoring found a
> bug in the CT truth: the cranial cavity was filled one axial slice at a time, so any slice with
> an open bone ring (frontal sinus, orbit roof, crop) split the cavity into slabs and only the
> largest slab was kept (for example 268 mL instead of about 1,330 mL). The inner/outer skull
> truth surfaces were therefore wrong in many cases, and the 6 failures came from the same bug.
> The fix is in `soma.benchmarks.ct_skull` with a regression test. The MR/CT consistency flag
> was also found not to be meaningful (bright diploic marrow on T1). Protocol v2 replaces v1.
> The numbers below are kept as the historical v1 record only.

## Outcome (v1, superseded)

**Readiness of the T1-only baseline: `NOT_READY`.** Every decision check fails.

| Count | Cases |
|---|---:|
| Requested (all brain cases with MR, CT and mask) | 180 |
| Scored | 174 |
| Failed: no surface inside the evaluation region | 6 |
| Unflagged (primary analysis) | **0** |

## Why the primary analysis is empty

The sealed exclusion flags fired on every scored case:

| Flag | Cases flagged |
|---|---:|
| Vertex truncation (tissue or bone in the top 3 slices) | 173 |
| Skull defect (uncovered cavity patch ≥ 200 mm² or cavity < 900 mL) | 122 |
| MR/CT consistency (< 50% of CT bone dark on T1) | 82 |
| Metal (> 10 voxels ≥ 3000 HU in region) | 14 |

SynthRAD2023 crops its volumes close to the head, so scalp tissue reaches the top slices in
almost every case; only 22 cases have bone there. The truncation rule as written (tissue
**or** bone) was therefore too strict for this dataset. This is a protocol design error found
after scoring. It is reported, not fixed, here: a corrected rule would be a new protocol version
written with these results already seen.

## All-cases sensitivity analysis (300 HU, 174 cases, flagged included)

Subject bootstrap means with 95% intervals. Negative signed distance = estimate inside CT.

| Boundary | Signed mean mm | Mean absolute mm | HD95 mm | Limit (mean abs / HD95) |
|---|---:|---:|---:|---|
| Inner skull | −1.86 (−3.16 to −0.47) | 5.84 (4.97–6.80) | 15.45 (13.26–17.80) | 2 / 5 |
| Outer skull | −5.70 (−6.37 to −5.05) | 6.18 (5.66–6.72) | 16.44 (15.06–17.73) | 3 / 7 |
| Scalp | −4.60 (−5.09 to −4.10) | 4.05 (3.73–4.35) | 15.56 (14.33–16.79) | 2 / 5 |

Skull thickness error: −3.97 mm (−4.37 to −3.54), i.e. the 6 mm offset prior makes the skull
about 4 mm too thin, and the estimated scalp sits about 4.6 mm inside the true scalp.

Even counting every flagged case, each boundary misses its limit by a wide margin, so the
`NOT_READY` label does not depend on the exclusion-rule error above.

## What this means

- Soma still has **no validated skull or scalp**. A T1 Otsu scalp plus a fixed-offset skull is
  not accurate enough for a conductor model, and the CT comparison now shows by how much.
- The realistic next step is a measured skull from MRI, for example FreeSurfer's watershed BEM
  (`generate_watershed`, which needs a FreeSurfer install and licence) or a learned
  skull segmenter, evaluated against the same CT benchmark under a new protocol version.
- The CT benchmark itself (`soma.benchmarks.ct_skull`) is now in place for that comparison.
