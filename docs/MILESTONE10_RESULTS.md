# Milestone 10 — independent references and off-grid benchmarks

Soma 0.10.0 continues baseline 144dcf7. The 495 original tests passed before work;
the [scientific protocol](MILESTONE10_PROTOCOL.md) was frozen before image/label
analysis. All old tests and M9 artifacts remain unchanged.

## Executed findings

* Actual official BrainWeb T1/1-mm/noise0/RF0 and matching discrete reference were
  loaded with their MINC geometry. All published tissue counts match. Global
  unsupervised T1 baseline macro Dice is **0.60190**; poor boundary metrics and
  extracranial false positives remain visible.
* Actual Mindboggle release-3 subject **NKI-RS-22-11** has native T1, manual DKT31,
  independent supplied classifier output, native/MNI assets and cortical surfaces.
  All **62 cortical targets** were scored after a justified exact grid reindex,
  with no fitted registration. Macro Dice is **0.92075**, mean ASSD **0.33788 mm**,
  mean HD95 **2.21242 mm**. This is not gold-standard tissue/skull segmentation.
* Thirty-six sampled analytic surfaces cover scalar/binary sphere, ellipsoid,
  asymmetric and nested-shell boundaries at 4/2/1 mm. Scalar sphere area/volume
  errors decrease, but binary area error worsens to 8.385%. Ten large cases leave
  full intersection checking unassessed; genus is not promoted for them.
* Five known-sphere defects are computationally repaired with zero vertex
  displacement; the valid control stays valid. Large holes and genuine crossings
  are rejected. A small cap still requires anatomical review.
* Continuous truth and reconstruction forwards are separately evaluated. The
  synthetic off-grid study has **462 rows / 4,851 source evaluations**; grid-only
  study **144 / 1,512**. A conditional participant example adds **32 BEM rows**.
  Every peak satisfies its nearest-grid lower bound. Finer grids commonly worsen
  peak error and attenuate nearest-vertex current; no unbiased-recovery claim.
* Boundary/registration and discretization/regularization interactions use paired
  draws and explicit assumptions, not an additive biological error budget.

## Reproducibility and limitations

Five report directories under `reports/milestone10-validated` hold source truth,
label/mesh arrays, tables, cache fingerprints, physical frames, input/output hashes,
software/code/Git identity and wall/CPU/RSS profiles. Registry listing is the sixth
requested CLI action. `experiments/milestone10/run.sh` reproduces the commands after
explicit fetch; supplemental contrasts have their own checked input/code hashes.
Large references/reports remain local, excluded from Git. The compact
[verification receipt](../experiments/milestone10/verification.json) records final
checks and actual metrics. Raw reference labels and prior unfavorable reports
were never overwritten. [Acquisition and implementation corrections](MILESTONE10_DATA_PROVENANCE.md)
are disclosed separately rather than rewriting the frozen protocol.

Single phantom/single human subject, shared classifier/annotation lineage,
finite surfel approximation, unknown cortical VTK-to-volume chain, unassessed
large-mesh intersections, spherical forward assumptions and borrowed off-surface
orientation priors limit interpretation. The real participant's anatomical BEM
readiness stays INDETERMINATE. Cortex validation does not certify skull/scalp.
No new PDE solver, full segmentation system, deep learning or fMRI GLM was added.

A proposed Milestone 11 would prospectively extend independent human tissue and
conductor-boundary references, multi-subject holdouts, justified cortical frame
chains and source-prior/grid normalization studies. It has not been started.
No remote push is included.


## Completed verification

The final suite passes **541 tests** (46 added; all 495 original tests retained),
including 15 opt-in integration cases, in 69.31 s. Ruff, formatting, strict mypy
(137 modules), and dependency checks pass. All five manifests identify the same
executed source tree and version 0.10.0. Verification checks 99 output hashes,
1,497 NPZ arrays and 15 visually reviewed figures; all 63 baseline M9 artifacts
remain unchanged. Local workflow times range from 0.62 s (grid study) to 53.57 s
(segmentation), with maximum process RSS 744.7 MiB for the conditional BEM study.
These exclude acquisition and initial cache construction. See
[verification](VERIFICATION.md#milestone-10--independent-references-and-continuous-sources)
for individual timings and their scope.
