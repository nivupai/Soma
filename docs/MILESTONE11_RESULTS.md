# Milestone 11 results — Soma 0.11.0

Baseline `0a4761d` passed 541 tests in 73.34 s. The M11 protocol and five
configurations were sealed before new reference scoring or holdout inspection.
All 42 baseline test files and 168 saved M9/M10 report files remain byte-identical.

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

Final full suite: **611 passed, 1 failed**, 60 warnings, 70.02 s; **71 new tests**
pass. The sole failure is the unchanged M10 test
`test_protocol_and_installed_version_match_source`, which explicitly requires
version `0.10.0`, incompatible with the requested installed/source `0.11.0`.
That assertion is retained under the strict requirement to preserve earlier tests.
No test is skipped, monkeypatched or weakened to conceal this conflict. All other
baseline tests, including cached M6–10 integration regressions, pass. Strict mypy
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
sensitivity, and the incompatible legacy version assertion. No anatomical or
clinical certification is implied. No remote push or M12 implementation.

Proposed M12: authorized subject-disjoint human tissue cohorts, documented SCI
label/frame/interface chains, independent conductor reference evidence, measured
cortical quadrature and a new prospectively specified regularization calibration
study. See [generalization limits](ANATOMICAL_GENERALIZATION.md).
