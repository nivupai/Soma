# MRI validation: Soma 0.7.0

The implemented scope is structural image geometry and conservative anatomical
modeling. It does not establish clinical segmentation, true anatomical registration
accuracy, valid individual EEG/MRI alignment or physiological conductor boundaries.
Successful and unfavorable numerical findings are retained together.

## Baseline, checks and artifacts

The clean Milestone 6 baseline was `8a5ca65`; all **362 existing tests passed
unchanged in 41.28 s** before implementation. The final MRI suite adds **59 tests**
for a total of **421 passing tests in 43.50 s**. The ordinary offline suite passes **410**
with **11 cached integration tests deselected in 30.30 s**. Full integration never fetches
MRI or anatomy; missing assets are skipped or reported with an explicit fetch
instruction. Ruff lint/formatting, strict mypy and dependency checks pass.

Executed verification includes NIfTI-1/2 I/O, scaling, explicit 4D selection,
conflicting/uncoded forms, truncated files, physical orientation/units, identity
and analytic interpolation, masks/labels, rigid/affine recovery, moment
initialization, native transform serialization with a nonzero center, sphere/
ellipsoid geometry, pathological mesh topology, triangle contacts, vertex-link
nonmanifoldness, containment, MRI-to-MNE interface checks and CLI help/error paths.
Actual CLI registration and surface extraction also completed on the derived real
MRI files. The latter reports invalid mesh quality rather than asserting validity.

The environment is Python 3.12.2, NiBabel 5.4.2, SimpleITK 2.5.7 and scikit-image
0.26.0. Strict checking remains enabled for Soma; untyped-call exclusions apply
only to these external library boundaries. The test run emits 56 upstream
scikit-image/NumPy 2.5 deprecation warnings about assigning ndarray shapes. They
are retained in logs; they do not represent failed tests or silently repaired data.

Verified reports live locally in `reports/milestone7-complete/`:

| Directory | Contents |
|---|---|
| `synthetic/` | Independent analytic registration truth, errors, failures, tissue levels, shell checks, surface convergence and four figures |
| `real/` | T1w inspection, controlled registration, coarse foreground mask/surface, mesh diagnostics and seven figures |
| `benchmark/` | Isolated lazy/eager processes, transform/resampling/registration/surface timings and memory |
| `source-forward-regression/` | Preserved fsaverage forward and diagnostic figures |
| `source-inverse-regression/` | Subject 1 runs 4/8/12 trial-wise MNE/dSPM source power |
| `cli-registration/`, `cli-surface/` | Actual command-level smoke artifacts |

The five main reports share source-tree SHA256
`b7100392af35daf75165914cf752b9a1add8af31813e945ee03d27d185fa7e60`.
Their manifests record Soma 0.7.0, full parameters, input identity, dependency
versions, seed, baseline Git revision and the honest pre-commit dirty state.
All recorded output checksums and pickle-free NPZ arrays were independently
verified. Eleven MRI figures covering all ten requested figure types were rendered
headlessly and visually inspected. No scientific computation required a 3D GUI.
A small committed `experiments/milestone7/verification.json` preserves the key
measurements; raw MRI, full arrays and local reports remain outside Git.

## Real dataset and NIfTI findings

The dataset is the SPM auditory BIDS **sub-01 T1w** anatomical image, from the
[official SPM auditory dataset](https://www.fil.ion.ucl.ac.uk/spm/data/auditory/).
Its terms allow personal educational/evaluation use; broader use requires contacting
FIL's methods group. This is not the SPM software license or an invented CC license.
The adapter uses exact HTTP ZIP ranges because fetching the complete functional
archive is unnecessary for this task; no Nilearn/full-series dependency was added.

- Archive URL: `https://www.fil.ion.ucl.ac.uk/spm/download/data/MoAEpilot/MoAEpilot.bids.zip`.
- Selected member: `MoAEpilot/sub-01/anat/sub-01_T1w.nii`.
- Archive ETag: `"1cc7499-2f0a032e93840"`; size 30,176,409 bytes.
- Retrieved archive metadata/anatomy bytes: **2,269,103**, with no functional files downloaded.
- Raw image SHA256: `20d1669c33b19393f98d2141e36ca99960bff41f3858f2cb274c697547fda224`.
- Shape **256×256×54**; spacing **1×1×3 mm**; stored signed big-endian int16.
- Scaling slope **0.125**, intercept **0**; scaled materialization naturally becomes float64.
- Coded qform and sform both have code **2** and agree; NiBabel selects sform.
- Native storage orientation is **LAS**, with RAS origin **(+127,−167,−72) mm**.

The negative storage determinant is valid and does not mean that the anatomy
was silently mirrored. Input transforms/units are preserved and source files
are never overwritten. Conflicting coded forms and unknown units are tested
with separate synthetic NIfTIs; they are not falsely reported as problems in
this real dataset.

## Coordinate and interpolation accuracy

Independent homogeneous-matrix tests cover axis permutations, negative storage
axes, anisotropic spacing, translation, rotation, shear and inverse composition.
NiBabel voxel-world coordinates agree with Soma, and SimpleITK physical index
points agree after explicit axis transposition and RAS/LPS/mm conversion.
Normals use inverse transpose; a sheared tangent remains orthogonal to its
transformed normal. Physical rigid transforms retain the Milestone 6 handedness
and proper-rotation restrictions.

The real MRI probe round-trip bound is **7.99×10⁻¹⁸ m**. A representative
100,000-point voxel/world round trip has maximum error **2.84×10⁻¹⁴ voxels**
(less than 9×10⁻¹⁷ m under the largest voxel spacing). These are numerical
geometry errors, not anatomical coregistration accuracy.

Identity nearest/linear and cubic resampling checks pass. A nontrivial affine
offset of an independently known linear intensity ramp matches its analytic
values. Label and boolean resampling uses nearest only, preserves IDs and rejects
unrepresentable background values. Integer intensity interpolation promotes
rather than rounding intermediate values. Repeated in-memory interpolation is
blocked unless explicitly acknowledged. NIfTI-1/2 writes preserve int64 values;
boolean masks use lossless uint8 storage. Source images remain immutable.

## Registration recovery

Moving asymmetric Gaussian phantoms are sampled independently from their known
physical transforms. The six pre-recorded small perturbations use identical
optimizer settings; the true transform is not used to tune initialization or
choose a favorable metric after observing errors.

| Model | Perturbation multiplier | Translation error | Rotation error | Median landmark TRE | Physical-region Dice before → after |
|---|---:|---:|---:|---:|---:|
| Rigid | 0.5 | 0.008 mm | 0.0238° | 0.011 mm | 0.8521 → 0.9872 |
| Rigid | 1 | 0.036 mm | 0.0256° | 0.035 mm | 0.7189 → 0.9892 |
| Rigid | 2 | 0.018 mm | 0.0239° | 0.020 mm | 0.4510 → 0.9872 |
| Affine | 0.5 | 0.022 mm | 0.0335° | 0.037 mm | 0.8541 → 0.9887 |
| Affine | 1 | 0.035 mm | 0.0588° | 0.078 mm | 0.7228 → 0.9897 |
| Affine | 2 | 0.035 mm | 0.0288° | 0.086 mm | 0.4456 → 0.9844 |

All six satisfy the pre-recorded median TRE limits (rigid <1 mm, affine <1.5 mm)
and rotation <1°. MSE decreases in every case. Separately estimated reverse
registration at multiplier 1 gives maximum composition displacement **0.073 mm**
(rigid) and **0.127 mm** (affine), rather than treating algebraic inversion alone
as independent recovery evidence. Algebraic inverse errors are near machine precision.

Failure/ambiguity cases remain explicit:

- Constant images are rejected before optimization.
- Severe perturbation/poor initialization completes numerically at its iteration limit but has **58.48-mm median TRE** and **82.18° rotation error**.
- A rotationally ambiguous sphere reaches a small-step stop yet has **1.61-mm median TRE** and **4.36° rotation error**.

The real T1w controlled-transform experiment has **0.403-mm translation error**,
**0.198° rotation error**, **0.354-mm median physical-point TRE** and **0.376-mm
maximum TRE**. Its final normalized mean-squares metric is approximately 0.0539,
with 149 recorded pyramid iterations and a small-step stop. Those test points
are physical probes, not manually annotated anatomy. This is a one-image artificial
motion experiment, not independent validation of clinical, cross-subject or
EEG-to-MRI alignment. Optimizer loss/convergence cannot establish such validity.

## Segmentation and surface findings

The synthetic noisy level phantom's threshold baseline gives **Dice=1, Jaccard=1**
for the specified synthetic region. It is not a GM/WM/CSF result. Region volumes
and the threshold/noise/seed provenance are saved. The real MRI has no supplied
reference segmentation, so no real reference Dice/Jaccard is invented.

The real mask uses native Otsu threshold **51.9961**, nearest resampling to a
5-mm grid, one voxel-neighborhood closing iteration, hole filling and largest
component selection. Eight components existed before selection; processing changed
5,168 coarse mask voxels. This is explicitly a coarse foreground/head envelope.
Its mesh has:

| Measurement | Result |
|---|---:|
| Vertices / faces / edges | 10,264 / 20,940 / 31,401 |
| Connected components | 1 |
| Boundary edges | 0 |
| Degenerate triangles | 0 |
| Duplicate faces | **6** |
| Nonmanifold edges / vertices | **9 / 12** |
| Inconsistent paired-edge winding | 0 |
| Euler characteristic | **−197** |
| Median triangle quality | 0.8165 |
| Reliable enclosed volume | **withheld (null)** |
| BEM readiness | **false** |

Closed edge counts or positive signed volume alone would have missed these defects.
No hidden smoothing/repair is used to claim a successful anatomical surface.
The implementation detects and reports invalid geometry, as required by the
conservative modeling scope.

Synthetic sphere/ellipsoid masks are connected, outward and closed under the
implemented checks, with Euler characteristic 2. Exact tetrahedron area/volume and
independent triangle contacts validate the measurement formulas. Binary sphere
area errors at 4/3/2 mm are **7.73/8.58/8.06%**, and volume errors
**0.51/1.26/0.66%**: the binary convergence expectation fails and is not hidden.
The subsequently added signed-distance sphere control has area errors
**0.555/0.316/0.140%** and volume errors **1.053/0.601/0.266%**, decreasing as
resolution improves. Binary rotated ellipsoid volume errors decrease
**1.164→0.813→0.239%**. Approximate ellipsoid surface area is not used as exact truth.

The three synthetic nested shells pass scoped topology, winding, separation and
containment checks. Both adjacent minimum triangle separations are **7.35 mm**,
above the required 1 mm. They are geometric candidates, not validated anatomical
conductors. The tolerance is 1e-8 m; scope limitations of adjacent-face intersection
checks are stated in MRI_SURFACE_MODELING.md. No actual BEM solution is built here.

## Performance and scaling

Measurements use one ITK/BLAS thread on the local macOS/Python 3.12.2 environment.
The standalone benchmark precedes the parallel final workflows.
Workflow report timers begin after module imports and, for real data, cached
dataset lookup; startup and downloading are outside those analysis timings. Warm-cache local
measurements are not performance guarantees or cold-network download timings.

| Representative benchmark | Measured wall time |
|---|---:|
| Lazy NIfTI metadata + input checksum | 6.03 ms |
| Eager scaled materialization after load | 9.62 ms |
| 100,000-point voxel→world→voxel | 6.89 ms |
| MRI → 5-mm reference-grid resampling | 17.01 ms |
| Coarse foreground marching cubes | 6.81 ms |
| That mesh's validation (20,412 faces) | 85.43 ms |
| 49³ asymmetric rigid registration | 1.056 s |
| Entire benchmark, including isolated loading processes | 1.819 s |

The isolated lazy process peaks at **67.5 MiB**, eager at **98.56 MiB**. Eager
materialization adds **33.81 MiB** to its own high-water measurement and exposes
**27 MiB** of scaled values; stored voxel bytes are **6.75 MiB**. Process baselines
vary, so these are not zero-overhead library or pure-array memory measurements.
The benchmark parent peaks at **307.05 MiB**. Final synthetic and real workflows
take **9.798/2.858 s** with **335.16/416.92 MiB** process peak RSS. Real resampling,
extraction and topology diagnostics take approximately **43.1/6.7/84.7 ms**;
real controlled registration takes 1.552 s in the concurrent final workflow.

Data materialization/resampling scales with voxel count; registration also scales
with sampled points, pyramid and iterations. Edge sorting/topology is approximately
O(F log F). Triangle checks use bounded pair batches and a conservative spatial
broad phase; worst-case intersection/separation work can still be quadratic.
Winding-number probes cost O(points×faces). Invalid real topology short-circuits
expensive self-intersection certification; its fast timing does not predict the
cost of a large valid anatomical surface. Full-resolution anatomical modeling
needs additional profiling and validation.

## Compatibility, limits and next milestone

No Milestone 6 source module was modified. The actual average-referenced
fsaverage lead field is **bitwise identical** to the v0.6.0 array, still 64×1,284
and rank 63. The subject-1 runs 4/8/12 MNE/dSPM trial-power demonstration completes
again with the same accepted epoch counts. Existing head/MRI rigid transforms
and the original 362 tests remain operational. New bridge checks reject mismatched
subject identity or incompatible frames and retain the MRI→MNE transform chain.

The real foreground is not a validated brain/skull/scalp segmentation. The mesh
kernel's scoped geometric checks are not a universal solid-geometry certificate.
The registration benchmark covers bounded same-modality perturbations; configurable
correlation/MI are not independently established clinical methods by this work.
In-memory resampling guards cannot recover unknown history from arbitrary files.
No actual SPM-to-PhysioNet coregistration, production tissue model, FreeSurfer
reconstruction, new BEM solver, deep-learning segmentation or fMRI GLM is added.

Proposed Milestone 8: participant-matched sensor/MRI coregistration and independent
validation of anatomical conductor boundaries using established tools, before
individual EEG forward inference. That proposal has not been started.

## Milestone 9 evidence audit

The matched sample's ico3 geometry remains computationally checked while anatomical
readiness remains INDETERMINATE. New evidence records distinguish verified geometry,
external asset provenance, same-pipeline derivative heuristics and missing independent
tissue/landmark truth. Brainmask/seghead foreground comparisons expose discrepancies,
not invented reference Dice values. Exact source-to-triangle clearance differs from a vertex
`mindist` setting; the additional finding is documented without altering M8 sources.
The original SPM foreground rejection is preserved. See ANATOMICAL_EVIDENCE.md and
MODEL_RELIABILITY_ADDITIONAL_FINDINGS.md.

## Milestone 10 external references

Actual original-normal BrainWeb MINC and discrete tissue codes were validated;
provided class counts match exactly. A limited unsupervised baseline is scored
without a reference ROI. Actual NKI-RS-22-11 native T1/manual DKT31 and separate
publisher classifier predictions cover 62 cortical labels, with exact explicit
world-grid reindexing, not fitted registration. Raw float-stored manual label IDs
are verified integral before conversion. Manual cortical labels do not validate
CSF/gray/white tissue or conductor boundaries. Original VTK coordinates remain
unmapped where their volume chain is unverified. See SEGMENTATION_BENCHMARKS.md,
SURFACE_TOPOLOGY_VALIDATION.md and MILESTONE10_DATA_PROVENANCE.md.
