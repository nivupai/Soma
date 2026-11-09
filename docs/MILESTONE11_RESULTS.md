# Milestone 11 results — Soma 0.11.0

Baseline `0a4761d` passed 541 tests in 73.34 s. The M11 protocol and five
configurations were sealed before new reference scoring or holdout inspection.
All 168 saved M9/M10 report files remain byte-identical. Of 42 baseline test
files, 41 are byte-identical; the sole authorized edit changes the version
assertion from 0.10.0 to 0.11.0.

## External reference and human evaluation

The actual official SCI corrected T1 and eight-label Seg3D segmentation were
loaded and checked: 208×256×256, finite scalar arrays, recorded file/archive
SHA256, label codes 1–8. Native connectivity is reported without guessing the
label ontology. T1 says LPS; the segmentation says only 3D-right-handed; physical
units are uncoded. One DICOM metadata slice supports 1 mm T1 acquisition, but
cannot establish segmentation orientation. SCI BEM readiness is INDETERMINATE.
No huge tetrahedral FEM mesh was downloaded or converted into three-layer BEM.

MRBrainS13 has no authorized local files. The frozen IBSR substitute's official
download requires NITRC login. Development IBSR_01 and holdouts IBSR_02/03/04
therefore have **no tissue scores**; missingness is retained in actual CLI reports.
No human cohort interval, population generalization or independent skull/scalp
validation is claimed. Adapters and analytical cohort tests do not replace data.
See [external reference evidence](EXTERNAL_HEAD_MODEL_REFERENCES.md) and
[tissue policy](TISSUE_SEGMENTATION_VALIDATION.md).

## Source priors and physical sensitivity

Five block priors, raw/sensor-trace conventions, fixed/free representations,
three regularizers and 20/15/10 mm grids were executed. The main sweep has
**420 operators, 2,520 source rows, 52,920 single-source evaluations**, 1,260
paired noise contrasts and 300 correlated-pair time-series cases. There were no
numerical failures. Grid-priors repeats the shared-conductor subset: 180 operators,
1,080 rows/22,680 evaluations; these are not independent extra experiments.
Grids contain 146/340/1,188 source points and are not all nested. Continuous truth
was independently evaluated off-grid with .5 mm separation checks; no interpolated
reconstruction columns were used. Shared MNE isotropic sphere assumptions remain.

Uniform-prior free-orientation source 0, normal-aligned, lambda2=1/9, no noise:

| Grid | Raw peak error | Normalized peak error | Raw nearest moment ratio | Normalized ratio |
| --- | ---: | ---: | ---: | ---: |
| 20 mm | 11.789 mm | 11.789 mm | .08614 | 3.34e-8 |
| 15 mm | 9.949 mm | 12.124 mm | .04509 | 1.35e-8 |
| 10 mm | 21.886 mm | 11.789 mm | .01342 | 3.55e-9 |

Sensor-trace normalization meets target 1 to maximum absolute error **6.66e-16**.
It does not deliver unbiased amplitude or grid invariance: the frozen physical
alpha is held against the raw 20-mm reference, so rescaling prior variance changes
effective regularization and strongly shrinks currents. This unfavorable outcome
is retained. Across primary uniform paired-noise configurations, normalized-minus-
raw mean peak contrasts range **−16.136 to +59.994 mm**; no universal winner is
selected. Other policies, orientations/depths, noise covariance mismatch and model
mismatch are exploratory sensitivities, with all noise intervals and PSF metrics
saved. Single-source primary estimates use peak-phase snapshots; correlated-pair
cases use the saved full 10-Hz, 100-Hz-sampled, one-second waveforms (correlation .8).

Independent diagonal/low-rank/scaling/basis oracles pass. Equivalent public MNE
uniform-prior kernels agree within **7.13e-14** relative error over three lambdas.
This equivalence uses depth=None, free orientation, rank23, average reference and
the documented trace/rank alpha; it does not identify custom area/depth policies
with MNE's depth .8 implementation. Area-informed volumetric experiments use an
explicit spherical quadrature convention, not measured cortical patches.

Known synthetic shells pass the existing BEM readiness checks. Recomputed BEM
leads on the 10-mm Cartesian grid change **5.214%** for brain radius +1 mm and
**28.581%** for halved skull conductivity, preserving source/electrode ordering.
These are physical numerical controls, not measured anatomical variation. External
human conductor-to-forward sensitivity remains incomplete.

## Verification, cost and incomplete criteria

Final full suite: **612 passed**, 60 warnings, 74.23 s; **71 new tests**
pass. The user authorized changing only the M10 version assertion to 0.11.0.
Every other baseline test remains unchanged. The earlier 611-pass/1-failure run
is retained in the verification receipt as historical evidence; the version
conflict is resolved. Cached M6–10 integration regressions pass. Strict mypy
passes 146 modules; Ruff, formatting and dependency checks pass.

| Workflow | Wall time | Peak process RSS |
| --- | ---: | ---: |
| Tissue missing-data report | .080 s | 184.0 MiB |
| External conductor inventory + synthetic physical control | 2.339 s | 386.3 MiB |
| Main prior study | 4.056 s | 280.7 MiB |
| Repeated grid-prior subset | 1.945 s | 244.7 MiB |
| Holdout missing-data report | .065 s | 182.9 MiB |

Times exclude acquisition/initial physical cache construction. RSS is process
high-water including libraries, not incremental allocation. One worker was used.
Six CLI actions produced real inventories, measurements or explicit unavailable
statuses under `reports/milestone11-final`. Sixteen figures were visually
inspected, with numerical companions; raw data/reports remain local and ignored.
The [verification receipt](../experiments/milestone11/verification.json) binds the
executed source tree, inputs, manifests, artifact hashes and checked arrays.

Incomplete acceptance: genuine human tissue scoring, multi-subject generalization,
SCI anatomical boundary/ontology/frame validation, external anatomical forward
sensitivity. The user confirmed no access to the registered tissue files. No anatomical or
clinical certification is implied. No remote push or M12 implementation.

Proposed M12: authorized subject-disjoint human tissue cohorts, documented SCI
label/frame/interface chains, independent conductor reference evidence, measured
cortical quadrature and a new prospectively specified regularization calibration
study. See [generalization limits](ANATOMICAL_GENERALIZATION.md).


## Human MRI reference integration addendum

This new local-data analysis continues baseline `10ead8c` and leaves every earlier
scientific report and frozen protocol unchanged. The new
[human protocol](MILESTONE11_HUMAN_PROTOCOL.md) was sealed before scoring. All 612
baseline tests remain unchanged. The aggregate-only
[verification receipt](../experiments/milestone11-human/verification.json) records
the new evidence; individual records/images and data hashes stay in ignored reports.

### Actual reference coverage and prediction independence

All **18 IBSR** subjects were evaluated as development data, using supplied stripped
T1 and the non-filled tissue reference. All **five MRBrainS labeled training**
subjects were externally evaluated using registered T1 and manual native eight-class
labels. Their training-directory three-class files confirm the mapping only; they
are never treated as an independent algorithm. All 30 extracted MRBrainS training
NIfTIs match their archive members. The 15 MRBrainS test folders, including label-named
files, were inventoried by filename only; no test header/payload/hash was read.
There were **23 completed subjects, 69 tissue rows and zero subject failures**.

The independent method is Soma's fixed global multi-Otsu baseline: subject T1
histogram only, 256 bins, foreground >2% maximum, ascending CSF/GM/WM classes.
No label-derived mask/threshold fitting, trained model, class permutation or
external-score tuning was used. IBSR upstream skull stripping shares dataset
preprocessing lineage; MRBrainS T1 remains full-head. Differences in scope and
acquisition prevent a controlled causal comparison of dataset means.

### Measured overlap, boundaries and volume

Subject-level mean macro Dice (2,000-draw bootstrap 95% percentile interval):

* **IBSR development: 0.58735** (0.57704–0.59846).

* **MRBrainS training external evaluation: 0.45568** (0.36191–0.54685).

Per-tissue entries below are means across subjects, not pooled voxel statistics.
Physical boundaries use area-weighted native voxel-face centers; masked MRBrainS
faces touching excluded voxels/FOV exterior are unobserved, not artificial matching
boundaries. HD95 is a pooled area-weighted percentile within each subject/tissue.

| Dataset | Tissue | Dice | Jaccard | ASSD (mm) | HD95 (mm) |
| --- | --- | ---: | ---: | ---: | ---: |
| IBSR | CSF | 0.1113 | 0.0596 | 26.785 | 43.372 |
| IBSR | gray matter | 0.7850 | 0.6476 | 1.097 | 3.296 |
| IBSR | white matter | 0.8658 | 0.7644 | 0.822 | 3.195 |
| MRBrainS | CSF | 0.4782 | 0.3145 | 5.611 | 21.202 |
| MRBrainS | gray matter | 0.5264 | 0.3583 | 7.720 | 32.547 |
| MRBrainS | white matter | 0.3625 | 0.2592 | 11.706 | 38.941 |

Volume differences use the determinant of each native physical affine. Signed
values are prediction minus reference; mL values below equal mm³/1,000.

| Dataset | Tissue | Mean signed difference (mL) | Mean absolute difference (mL) | Mean signed relative error |
| --- | --- | ---: | ---: | ---: |
| IBSR | CSF | 273.71 | 273.71 | +1572.0% |
| IBSR | gray matter | -234.53 | 234.53 | -27.0% |
| IBSR | white matter | 55.36 | 63.85 | +11.9% |
| MRBrainS | CSF | 531.88 | 531.88 | +131.1% |
| MRBrainS | gray matter | 599.53 | 599.53 | +117.3% |
| MRBrainS | white matter | 168.66 | 243.79 | +52.7% |

Poor results are retained. IBSR CSF is strongly overestimated relative to the
non-filled provided reference; the filled derivative was not substituted to
improve scores. MRBrainS full-head intensities produce substantial extracranial
confounds and very low WM overlap in some cases. Annotation coverage/conventions,
preprocessing and anisotropy also affect interpretation. No universal success or
population guarantee follows from these small cohorts.

### Geometry, restrictions and retained gaps

IBSR has coded sform, uncoded spatial units and singleton fourth dimensions;
frame0 and documented millimeter interpretation are explicit, without modifying
source headers. Native stripped/reference grids match without resampling.
MRBrainS labels remain fixed on the registered anisotropic grid. Coded sform is
selected with recorded qform disagreement; the largest inspected q/s corner
difference is about .4291 mm. Two T1 images require one identity-world linear
intensity resample under the frozen .05-mm alignment limit. Another extremely
small difference remains within existing Volume.same_grid tolerances. No fitted
registration, label resampling or outcome-based transform choice is performed.

The local MRBrainS Readme/manifest identify a compatible release and label policy,
but do not grant a license or prove portal authorization/history. This is the
user-requested local segmentation-methods evaluation; no broader commercial use
or redistribution is inferred. IBSR's local notice and requested citation are
preserved. No raw data, participant metadata, individual results or images are
committed. See [methods and access evidence](HUMAN_TISSUE_REFERENCE_METHODS.md).

Native training 7/8 cerebellum/brainstem are explicitly excluded from MRBrainS
scoring, not fed into prediction or relabeled as background truth. Per-subject
bootstrap uncertainty does not measure inter-rater uncertainty. Tissue annotation
and geometry agreement do not certify skull/scalp interfaces, conductivity,
conductor nesting, clinical reliability or BEM anatomical readiness, which remains
**INDETERMINATE**. No hidden-test challenge score is claimed.

### Verification and performance

**636 tests pass** (24 added; all 612 earlier cases unchanged), 62 warnings, 70.81 s. Ruff, formatting, strict mypy (149 modules) and dependency checks pass.
All 44 baseline test files and 224 historical report files are byte-identical.
Twenty-five final figures were reviewed; 174 output hashes and 290 finite,
pickle-free NPZ arrays were checked. The final source tree is shared across all
three new manifests and was fixed before external evaluation.

One post-review plotting correction separates undefined volume error from a valid
−100% prediction failure; it does not alter predictions or metric values. Final
reports were regenerated under the same frozen method and retain all 69 original
metric rows exactly. Regeneration is not an independent second validation cohort.

| Workflow | Wall time | Peak process RSS |
| --- | ---: | ---: |
| Inventory/archive/metadata checks | 0.974 s | 311.8 MiB |
| IBSR development | 83.676 s | 628.9 MiB |
| MRBrainS external evaluation | 37.765 s | 441.0 MiB |

Benchmark timings include loading, explicit alignment, prediction, scoring,
output writing and figures after input preflight; CLI startup and preflight hash
checks are outside those stage times. RSS is whole-process high-water including
libraries, not incremental memory. One worker was used; no network or new model
weights. Final private reports: `reports/milestone11-human-validated`, containing
per-subject/tissue CSV/JSON, native overlays, predicted label NIfTIs, validity masks,
input/output hashes, software/Git/source identity and stage timings. Existing
M11 reports remain historical. No remote push or Milestone 12 work is included.
