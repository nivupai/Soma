# M33 skull protocol: T1-only baseline head surfaces vs CT bone (draft — frozen only after owner approval)

Status: **DRAFT**. Nothing below has been scored. The T1-only baseline has not been compared
with any SynthRAD2023 CT. This file is sealed (SHA256 recorded in `configs/m33-skull-freeze.json`
by the owner-run `python -m scripts.seal_m33_skull --approved-by "<owner>"`) only after the owner
approves it. `scripts/run_m33_skull_validation.py` refuses to score until that seal exists,
says `owner_approved: true`, and matches this file's SHA256. Any later change is a new protocol
version and is reported as such. All numeric limits below are **proposals** for the owner to
accept or change before sealing.

## Question

Soma has no T1-only skull path: the only skull generator (`generate_watershed`) needs
FreeSurfer. How far are the surfaces of an explicitly labelled T1-only geometric baseline
(`soma.anatomy.t1_skull`) from independent CT bone truth, per boundary (inner skull, outer
skull, outer scalp), and is that close enough for the baseline to leave `NOT_READY`?

The baseline's outer skull is an **offset prior, not a measurement**. Its provenance says
`method: "T1-only geometric baseline; outer skull is an offset prior, not measured"` and
`readiness: "NOT_READY"` until this protocol says otherwise.

## Dataset

SynthRAD2023 Task 1, brain: paired `mr.nii.gz` (T1), `ct.nii.gz` (HU) and `mask.nii.gz` per case
on identical grids (1 mm, LPS voxel order, qform-coded, mm units), at
`data/external/synthrad2023/brain/<case>/` (git-ignored). Licence CC BY-NC 4.0: only cohort
aggregates may be committed or published; per-case outputs stay under the ignored
`reports/milestone33/skull/`. Every case with all three files is requested; no case is removed
by hand. The local copy currently holds centre A cases only; the runner stratifies by whatever
centres are present.

Stratification: by SynthRAD centre letter, the third character of the case id
(`1BA…` → A, `1BB…` → B, `1BC…` → C).

## Methods (fixed before scoring)

### Estimator (T1 only; never sees CT)

Default `T1SkullParameters`, all recorded in per-case provenance:

| Step | Rule |
|---|---|
| Inner skull | SynthSeg 2.0 robust (`--parc` off) on `mr.nii.gz`; labels > 0 (incl. extracerebral CSF 24), nearest-neighbour to the T1 grid, closing 2 voxels, hole fill, largest component |
| Scalp | T1 Otsu threshold on the unpadded T1 → `process_mask` (closing 3 voxels, fill, largest component) on a grid padded by 4 voxels |
| Outer skull | inner skull grown by **6 mm** (physical distance), clipped to stay ≥ **2 mm** inside the scalp; inner skull kept ≥ 1 mm inside the clipped outer skull |
| Surfaces | `extract_surface` (marching cubes 0.5), `smooth` 10 iterations, step 0.1; MNE ids 1 inner skull, 3 outer skull, 4 scalp (`ConductorSurfaces.from_mne` convention), coord_frame 5 |

SynthSeg command template (absolute paths):
`<abs-path>/run-synthseg.sh --i {input} --o {output} --robust --threads 8`.

### CT truth (never sees the estimator)

Default `CTSkullParameters`:

| Boundary | Rule |
|---|---|
| Bone | HU > **300** inside `mask.nii.gz`; closing 2 voxels; largest component; enclosed holes ≤ 5 mL filled (diploe) |
| Inner skull | axial-slice hole fill of the bone after an enclosure closing of 5 voxels (bridges foramina/sutures for enclosure only), minus bone; 3D hole fill; largest component |
| Outer skull | outer boundary of filled (bone ∪ cavity) |
| Scalp | HU > −200 inside the mask; closing 3 voxels; fill; largest component |

Surfaces as for the estimator. Sensitivity: the whole truth rebuilt at bone HU **200** and
**400** (same region, same estimator).

### Evaluation region (fitted on CT only, identical for all boundaries and thresholds)

`RegionRule` in RAS+ world mm (superior +z, anterior +y), fitted on the 300 HU CT cavity:

- intracranial extent: from the lowest 1 mm axial level whose cavity cross-section is ≥ 25% of
  the maximum (ignores the spinal canal) to the top of the cavity;
- exclude everything below **40%** of that extent;
- exclude an anterior-inferior face/orbit/defacing box: anterior of 60% of the
  posterior→anterior cavity span **and** below 65% of the intracranial extent.

The fitted plane and box are recorded per case.

### Exclusion flags (automatic, reported, never silently dropped)

| Flag | Rule (proposed thresholds) |
|---|---|
| Metal | > 10 voxels with HU ≥ 3000 inside the evaluation region (total count also reported) |
| Vertex truncation | any tissue (HU > −200) or bone voxel inside the mask in the 3 most superior slices (superior end found from the affine; SynthRAD stores LPS so this is the last k slices) |
| Skull defect | an uncovered patch of the cavity boundary (no bone within 3 voxels) ≥ 200 mm² in the region, **or** cavity < 900 mL |
| MR/CT consistency | fraction of eroded CT bone (region) that is dark on T1 (< 0.5 × T1 Otsu inside the mask) < 0.5 |

Primary analysis: unflagged cases. Sensitivity: all cases including flagged ones. Every flagged
case is listed with the flags that fired.

## Metrics

Per case, per boundary, inside the evaluation region, distances in mm, area-weighted over
triangle centroids (as `surfels`/`_quantile` in `soma.benchmarks.segmentation`):

- **signed mean distance**, estimate → CT (positive = estimate outside CT). Sign from
  `contains` (generalized winding number) on the CT mesh; on large meshes, the trilinear CT mask
  at level 0.5, with `contains` audited on 256 seeded points and the agreement reported;
- **mean absolute distance**, symmetric (both directions pooled, area-weighted);
- **HD95**, symmetric (max of the two directed area-weighted 95th percentiles);
- **skull thickness error** along outward CT inner-skull vertex normals: shell length (outer
  minus inner skull) on the same ray, window −10 to +25 mm, step 0.25 mm; estimate − CT.

Cohort: subject-level seeded bootstrap (`soma.validation.cohort.subject_interval`, seed 11042,
2,000 repetitions) of each per-case metric; overall and per centre.

## Decision rule (proposed numbers)

Applied to the primary analysis (300 HU, unflagged cases), for the **T1-only baseline method
only**:

- **VALIDATED** if at least 15 cases are evaluable and
  - inner skull and scalp: mean absolute distance ≤ **2 mm** and HD95 ≤ **5 mm**, each with
    the bootstrap 95% upper bound also below the limit; and
  - outer skull: mean absolute distance ≤ **3 mm** and HD95 ≤ **7 mm** (upper bounds below),
    and the bootstrap 95% interval of the mean thickness error inside ±**2 mm**.
- **QC_ONLY** if the inner-skull and scalp criteria pass but the outer-skull/thickness criteria
  do not: the surfaces may be used for quality control and visualisation, not as a validated
  conductor skull.
- **NOT_READY** otherwise (including fewer than 15 evaluable cases).

The 200/400 HU and all-cases results are reported next to the primary result and do not
change the decision; a decision that flips under them is called out in the report. No result
here changes any other head model's readiness.

## Reproduction

After the owner seals this file and SynthSeg is installed locally:

```sh
python -m scripts.run_m33_skull_validation \
  --synthseg-cmd "<abs-path>/run-synthseg.sh --i {input} --o {output} --robust --threads 8" \
  --data-root <abs-repo>/data/external/synthrad2023/brain \
  --output reports/milestone33/skull
```

Per-case JSON goes to `reports/milestone33/skull/cases/<case>/skull-metrics.json` and the cohort
to `reports/milestone33/skull/cohort-summary.json` (both git-ignored). `--check-nesting` adds the
full `nested_boundaries` geometric check of each estimate (slow on 1 mm heads; recorded either
way). A second cohort run into the same output is refused.
