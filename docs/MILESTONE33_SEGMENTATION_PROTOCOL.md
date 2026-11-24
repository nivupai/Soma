# M33 segmentation protocol (draft — frozen only after owner approval)

Status: **DRAFT**. Nothing below has been scored. No new method has been run against any
IBSR or MRBrainS reference label. This file is sealed (SHA256 recorded in
`configs/m33-segmentation-freeze.json`) only after the owner approves it; any later change is a
new protocol version and is reported as such.

## Question

Does a pretrained, contrast-agnostic segmenter (SynthSeg 2.0) give better CSF / gray matter /
white matter labels than Soma's frozen multi-Otsu baseline on the same 23 labeled human cases,
and how much of the baseline's error is caused by missing head/brain masking alone?

## Cases and splits

| Dataset | Cases | Image | Reference | Role |
|---|---:|---|---|---|
| IBSR V2 | 18 | `IBSR_xx_ana_strip` | `IBSR_xx_segTRI_ana` | development (may be inspected to debug the runner) |
| MRBrainS13 training | 5 | `T1.nii` (full head) | `LabelsForTraining.nii` | **held-out**: scored once, after the IBSR run is final |

Same inventory, geometry checks and partition rules as the sealed M11 addendum
(`configs/human-tissues.yaml`). MRBrainS test-partition payloads are never read. No method in
this protocol is trained or tuned on any of these labels.

## Methods (fixed before scoring)

1. **Control: frozen multi-Otsu** (`soma.benchmarks.segmentation.intensity_baseline`), unchanged.
2. **Ablation: masked multi-Otsu.** The same function and thresholds rule, but only voxels inside
   an intracranial mask are classified; everything else is background. The mask is SynthSeg's
   non-background region (labels ≠ 0), dilated by 1 voxel. It never uses a reference label or a
   dataset-supplied brain mask. Purpose: measure how much of the gap is masking alone.
3. **Primary: SynthSeg 2.0** (robust mode, `--parc` off), run on the same image the control
   sees, imported through the `Precomputed` backend with full provenance (tool version, git
   commit, model file SHA256, input SHA256). SynthSeg output (1 mm) is mapped back to the native
   grid by nearest-neighbour resampling of labels; the transform is recorded.

### Ontology map, SynthSeg → Soma (written before scoring)

| Soma tissue | SynthSeg labels |
|---|---|
| CSF (1) | 4, 5, 43, 44 (lateral ventricles + inferior horns), 14, 15 (3rd, 4th ventricle), 24 (extracerebral CSF) |
| Gray matter (2) | 3, 42 (cerebral cortex), 8, 47 (cerebellar cortex), 10, 11, 12, 13, 17, 18, 26, 49, 50, 51, 52, 53, 54, 58 (deep GM, hippocampus, amygdala, accumbens), 28, 60 (ventral DC) |
| White matter (3) | 2, 41 (cerebral WM), 7, 46 (cerebellar WM), 16 (brainstem) |
| Background (0) | 0 and anything else |

Reference maps stay as already sealed: IBSR codes 0–3 identity; MRBrainS `{1,2}→GM, {3,4}→WM,
{5,6}→CSF`, with native 7/8 (cerebellum, brainstem) excluded from the scoring domain.

Known reference limitation, stated before scoring: IBSR's CSF class covers mainly ventricular and
some sulcal CSF, not the full subarachnoid space. Any method that labels extracerebral CSF
(as a conductor model should) will be penalised on IBSR CSF. This is reported, not corrected
for; the IBSR scoring domain stays the whole grid, as in M11.

## Metrics

The existing `soma.benchmarks.segmentation.score`, unchanged: Dice, Jaccard, HD95, ASSD,
surface Dice at 1 and 2 mm, signed and absolute volume error, per tissue and per case.
Cohort summaries: subject-level seeded bootstrap (seed 11042, 2,000 repetitions), as in M11.
Paired method differences (SynthSeg − control) per tissue, with bootstrap 95% intervals.

## Decision rule

- **Adopt SynthSeg** as Soma's default human segmenter if, on the held-out MRBrainS cases, its
  mean Dice beats the control for **every** tissue (CSF, GM, WM) and its mean HD95 is lower for
  every tissue.
- If it wins on some tissues and not others, the report says exactly which, and the owner decides.
- Secondary, descriptive targets (not pass/fail): held-out Dice ≥ 0.80 GM, ≥ 0.85 WM, ≥ 0.60 CSF.
- Multi-Otsu stays in the codebase as the control for all later milestones.
- No result here changes any head's readiness label; that is workstream B's job.

## Reproduction

One command, from the repository root, after SynthSeg is installed locally:

```sh
python -m scripts.run_m33_segmentation --synthseg <path-to-run-script> --output reports/milestone33/segmentation
```

Outputs per case and cohort, under ignored local storage; only aggregates are committed.
