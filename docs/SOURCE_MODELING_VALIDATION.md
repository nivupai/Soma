# Source-modeling validation: Soma v0.6.0

This is a template-based methodological demonstration. Numerical agreement
validates the implemented operators; it does not validate the anatomical
locations of neural generators in participant 1.

## Evidence and reproducibility

The clean v0.5.0 baseline was commit `6bc9999`; all 312 existing tests passed
before edits (33.30 s). The sealed source protocol preceded real source analysis.
Its canonical configuration SHA256 is
`cd72d9346de6359dc037ade8b6c9a47e490d362690642ace23508c8ef72e455b`.
The freeze receipt also binds the original document and raw YAML file hashes.

Final complete verification: **362 passed in 48.34 s**, including all 312
unchanged baseline tests and 50 new source tests. The ordinary offline suite
passes **352 tests with 10 integration tests deselected in 26.63 s**. Ruff lint and formatting checks
pass; strict mypy passes (83 source modules); `pip check`
reports no broken requirements. Source CLI help/error smoke tests pass. All
four scientific workflows completed on actual cached anatomy/EEG assets; no
mocked forward was substituted for the template integration.

The four verified reports share source-tree SHA256
`fde3aa7b7ef6f370faa166208950ebfccbcdd6474738d8a7f66745a028a37374`,
Soma 0.6.0, MNE 1.13.2 and nibabel 5.4.2. Reports honestly record the pre-feature
Git revision and dirty state. All manifest file hashes were independently
rechecked, and all NPZ arrays load with default `allow_pickle=False`.

Local full artifacts are deliberately ignored by Git:

| Workflow | Results |
|---|---|
| Geometry/forward and five figures | `reports/milestone6-verified/forward/` |
| 280 synthetic cases, truth, mismatch and sphere control | `reports/milestone6-verified/simulation/` |
| 12 PSFs/CTFs × five regularization settings | `reports/milestone6-verified/resolution/` |
| Subject 1 runs 4/8/12, MNE/dSPM trial power and ROIs | `reports/milestone6-verified/inverse/` |
| Standalone fresh BEM forward and 24 toy benchmarks | `reports/milestone6-final/benchmark/` |

A small committed `experiments/milestone6/verification.json` preserves the key
numbers and links them to report manifests. Large anatomical files, EDFs,
lead-field/inverse arrays and power arrays are not committed.

## Coordinate and forward checks

Rigid composition/inversion agrees with MNE's column-vector convention, with
round-trip tests at 10⁻¹⁵ m absolute tolerance. Incompatible frames, mm-as-m,
reflections, nonrigid scaling supplied as rigid, nonfinite data, singular matrices
and duplicate sensor/source identities are rejected. The supplied fsaverage
FIF rotation has a 2.59×10⁻⁷ RᵀR discrepancy, within the documented 5×10⁻⁷
rigid tolerance. No affine scaling is used for coregistration.

The actual `fsaverage_1005` geometry has 64 sensors. Approximate nearest
scalp-vertex distances are median **1.392 mm**, maximum **2.255 mm**; minimum
interelectrode separation is **28.211 mm**. Maximum coordinate discrepancy
between the montage's fiducial-derived native transform and the supported
fsaverage transform is **1.023 mm**. This is recorded, not called a registration
error estimate. Sensors are template based, not individually digitized.

MNE's genuine three-shell fsaverage BEM forward retains **1,284 ico3 white
vertices** (642 per hemisphere): fixed-normal L is **64×1,284**, free L is
**64×3,852**. The actual stored outer-to-inner conductivities are approximately
**0.3/0.006/0.3 S/m**. No arbitrary scalar alteration of this BEM was used.
Average referencing leaves **rank 63**, with retained condition number **355.34**.
The system remains severely underdetermined. The numerical projector sum/null
check passes; all lead-field values are finite. Fixed normal columns match
free-basis normal columns; hemisphere/vertex order is checked against inverse STCs.

Fresh and cached forwards agree at explicit FIF serialization tolerance
(rtol 5×10⁻⁵, atol 2×10⁻⁵ V/(A m)); cache corruption is rejected before FIF
parsing. Independent MNE noiseless source simulation agrees with the unreferenced
lead field and, after explicitly restoring average-reference projections, the
referenced field (atol 10⁻¹⁸ V). MNE's simulator deliberately removes input
projectors, so applying an absent projector is not a valid reference check.

## Inverse, covariance and analytical benchmarks

The small SVD reference is checked against identity and diagonal closed forms,
weighted normal equations, overdetermined exact recovery, underdetermined
minimum-norm forward consistency, rank deficiency and ill conditioning. It also
covers correlated noise, wrong covariance, wrong forward models, fixed/free
representations, zero noise, and zero/large regularization limits. Exact current
recovery is required only when identifiability permits it. Across identifiable
zero-regularization benchmark cases, maximum relative current error is
**1.52×10⁻¹⁵**.

Covariance tests reject asymmetry/indefiniteness, channel-order mismatch and
projector inconsistency. General SSP/reference null directions are retained as
null directions during shrinkage. Independent and MNE whiteners agree on the
retained subspace. Real rest covariance rank is 63 in every run; retained-space
whitening identity errors are **1.28–1.34×10⁻¹³** (Frobenius norm).
MNE kernel application agrees with direct signed fixed and Cartesian-vector
inverse application after explicit surface-basis conversion. dSPM is finite and
labeled dimensionless; it is not interpreted as current.

## Synthetic findings, including poor recovery

The predeclared seven scenarios, four SNRs and ten paired noise realizations
produce **280 cases**, with independent 16,000-sample covariance training.
Every case retains source IDs, orientations, phases, current amplitudes, burst
intervals, scalp-clearance depth proxies and evaluation seeds. Truth is used to
control simulated SNR, never to choose the primary λ²=1/9 or depth=0.8.

| Scenario | Peak error at −10 dB | At 0 dB | At 10 dB | At 20 dB |
|---|---:|---:|---:|---:|
| Focal | 88.27 mm | 13.20 mm | 1.14 mm | 0.00 mm |
| Amplitude modulated | 88.27 mm | 12.59 mm | 0.00 mm | 0.00 mm |
| Bursts | 88.27 mm | 9.71 mm | 0.00 mm | 0.00 mm |
| Correlated pair | 87.99 mm | 13.15 mm | 12.01 mm | 9.17 mm |
| Separated pair | 92.40 mm | 51.60 mm | 71.27 mm | 71.27 mm |
| Deep/shallow pair | 40.21 mm | 32.99 mm | 32.99 mm | 32.99 mm |
| 5% operator mismatch | 88.27 mm | 10.85 mm | 0.00 mm | 0.00 mm |

Values are mean assigned Euclidean peak error across ten realizations, not
anatomical accuracy estimates. The pair metric uses peak exclusion and assignment;
it can select a second peak within a broad blob instead of finding the weaker
source. The poor separated/depth results are retained, not tuned away. Selected
deep/shallow scalp-clearance proxies are approximately 83.63/19.26 mm.

At 10 dB the focal recovered time course correlates **0.9908** with truth, yet
full current relative error is **0.9891** and current norm at the true vertex is
biased by approximately **−97.9%**. A correct peak and waveform do not imply
correct amplitude or a concentrated source distribution.

The abstract mismatch has exactly **5% relative Frobenius perturbation**; its
singular-spectrum and row-subspace changes are saved separately. This particular
stress need not displace a peak at high SNR. The independent physically
recomputed four-shell sphere control changes skull conductivity 0.004→0.012 S/m,
changing the lead field by **21.74%** and the reconstructed current vector by
**29.51%** in its fixed test. Peak displacement is zero in that small control.
Its nearly zero column-subspace angles reflect a saturated referenced sensor
subspace and are not evidence that the models have equivalent source fields.

## Resolution and regularization

Twelve selected cortical columns and rows are evaluated at λ²=
0.0001, 0.01, 1/9, 1, 10. No full cortical resolution matrix is allocated.
At the primary λ²=1/9, mean selected-source peak Euclidean error is **18.82 mm**,
Euclidean dispersion **41.27 mm**, within-hemisphere mesh-edge geodesic dispersion
**70.79 mm**, and off-target energy fraction **97.33%**. Cross-hemisphere
geodesics remain undefined and contralateral leakage is separately measured.

Across λ²=0.0001→10, mean Euclidean dispersion grows **35.15→63.99 mm** and
off-target energy **94.03→99.47%**. Peak error is not monotonic and does not
summarize resolution on its own. In the focal depth-0.8 sensitivity probe,
sensor-noise amplification decreases **0.0300→0.000105 A m/V**, while PSF
Euclidean dispersion increases **28.21→66.11 mm**. Residual rises and current
penalty falls. Both depth settings and every λ² are reported without using
truth to promote a best setting.

## Real motor-imagery demonstration

Existing filtering, event, QC and epoch APIs were reused unchanged, with source
montage replacement explicitly confined to this workflow. All 30 proposed epochs
per run were logged. Accepted counts are:

| Run | T0 rest | T1 imagined left fist | T2 imagined right fist | Total |
|---|---:|---:|---:|---:|
| 4 | 7 | 4 | 2 | 13 |
| 8 | 10 | 7 | 5 | 22 |
| 12 | 10 | 7 | 6 | 23 |

There are **58 accepted epochs**, including 27 rest and 31 imagery epochs.
MNE and dSPM individual-trial vertex mu/beta powers, event indices, background
covariances, descriptive template precentral ROI features (464 rows), and
equal-run log-ratio maps are saved. The precentral labels come from fsaverage
aparc and are hashed. Condition counts are small and unequal, especially run 4.
There is no population or vertexwise significance test.

The physical MNE sensor residual averages **0.3773/0.3711/0.3702** in runs
4/8/12. This is regularized forward fit, not error against unknown true currents.
Same-kernel evoked/mean-source linearity errors are **6.5×10⁻¹⁶–9.7×10⁻¹⁶**
across methods/runs. In the all-condition pooled comparison, evoked mu power is
only **4.0–7.3%** of mean individual-trial source mu power; beta is **4.3–8.0%**.
This illustrates why a mean waveform is inadequate as the sole oscillatory
analysis, but real power reduction also includes noise averaging and mixed
conditions. The opposite-phase sinusoid test isolates exact phase cancellation.

Both template precentral ROIs have negative descriptive mu imagery/rest log
ratios across these runs. This observation is not an individualized motor-cortex
activation map. Broad resolution, background neural covariance, template and
sensor mismatch, trial selection and source nonuniqueness prevent such a claim.

## Figures and performance

All ten requested figure types were generated and visually inspected: electrode/
head geometry, coordinate frames, cortical source space, lead field, singular
spectrum, regularization tradeoff, synthetic recovery, PSF, error versus SNR and
exploratory trial-power maps. No 3D graphics backend was needed. Each figure has
its numerical NPZ companion and shared geometry/vertex identifiers. Superior
projections are labeled as overlapping cortical depths, not inflated cortical
surface renderings. Scientific arrays remain available without parsing images.

One-job BEM and `OPENBLAS_NUM_THREADS=1` were used. Python 3.12.2 on the local
macOS machine; these are measurements, not performance promises. Parallel final
workflow processes can contend for CPU, so the standalone fresh BEM benchmark
is the appropriate forward timing.

| Task | Wall time | Process CPU | Process peak RSS |
|---|---:|---:|---:|
| Standalone fresh BEM forward, including geometry and source loading | 2.285 s | 2.253 s | 588.0 MiB |
| Forward report/figures after preparation | 1.418 s | 0.893 s | 427.4 MiB |
| 280 simulations + sensitivity/figures | 5.117 s | 4.073 s | 426.4 MiB |
| Selected resolution + mesh geodesics | 3.041 s | 2.305 s | 422.1 MiB |
| Three real runs, both methods + power/figures | 3.658 s | 2.573 s | 487.2 MiB |

Analysis/report timings exclude initial forward preparation and EDF loading;
preparation adds about 0.94–0.99 s in the verified cached workflows. RSS is a
process high-water measurement including libraries and preparation, not an
incremental stage allocation. The fixed/free matrices occupy approximately
0.627/1.881 MiB. Download size and setup time are outside these timings.

## Limits and remaining work

The methodological scope is complete. Participant anatomy processing,
individual electrode measurement/coregistration, conductivity uncertainty studies
on independently reconstructed head models, external anatomical validation and
population source inference remain future work. No registration, segmentation,
FreeSurfer reconstruction, FEM solver or Milestone 7 was implemented. The source
API is prepared to accept independently validated MNE participant anatomy, but
template evidence cannot stand in for that validation.
