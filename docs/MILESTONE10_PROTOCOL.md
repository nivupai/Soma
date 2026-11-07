# Milestone 10 prospective validation protocol

Baseline: Soma 0.9.0, 144dcf7, 495 tests. This record follows inspection of M9
results, official reference metadata, archive directories and label/training-list
definitions. It precedes downloading/analyzing image or label contents and all
new numerical experiments. No old report, test, public contract or limitation is
replaced. This is a methods study, not anatomical or clinical certification.

## Reference standards and acquisition

BrainWeb: official McGill original normal anatomical model, 1-mm isotropic,
Talairach grid 181×217×181, start XYZ [-90,-126,-72] mm. Select T1 simulation
1-mm, noise 0%, RF nonuniformity 0% and the matching discrete anatomical phantom.
MINC is primary; raw byte is permitted only with explicit official dimension,
axis/start/step and intensity-scaling metadata. Ground truth is the provided
integer dominant-tissue class, not an intensity threshold. Fuzzy memberships are
available but are not falsely substituted for the discrete classification target.
Labels: 0 background, 1 CSF, 2 gray, 3 white, 4 fat, 5 muscle/skin, 6 skin, 7 skull,
8 glial, 9 connective. Score CSF/gray/white separately over the whole supplied grid.
The model is simulated reference anatomy, not independent human tissue histology.
Archive hashes bind this mutable service; no fictitious release identifier.
Official citation requested; no standard SPDX license was located. Keep raw assets
local, record download terms, and do not redistribute them in Git.

Mindboggle-101 release 3 (2019-04-03), author OSF nhtur and author Zenodo record
22070005: select **NKI-RS-22-11** only. Use its native T1 and manually edited DKT31
cortical labels, with the supplied JTAtlas40+aseg classifier prediction from the
DKT classifier-evaluation distribution. Check documented training/test membership
and report any uncertainty about lineage. No reference-self evaluation counts as
prediction validation. Preserve original label IDs. Evaluate the DKT31 ontology:
left IDs 1002,1003,1005..1031,1034,1035 and corresponding right IDs +1000 (62 labels).
Do not evaluate these as CSF/gray/white or certify skull/scalp segmentation.
Inventory native/MNI and cortical-surface assets separately; select compatible
native-space pairs, no opportunistic space choice by metric. Manual labels, image
and externally generated predictions remain distinct roles. Supplied reference
parcellation and classifier training may share project lineage, so do not claim
fully independent generalization without evidence.

The current author license is CC BY 4.0, with author/paper/source-project attribution
and modification notices. Exclude separately licensed OASIS subcortical labels and
original raw scanner archives. Download only selected entries using HTTP ranges
where supported. If an independently compressed cohort container is unavoidable,
fetch only the NKI-RS-22 container and extract this subject, recording transport
bytes versus retained subset. Never download the whole dataset automatically.
Budget: <=3 GiB new reference transport/cache, <=2 GiB per active process, one worker.
Missing, blocked or unverifiable inputs are explicit incomplete acceptance, never
invented ground truth. Metadata discovery/downloads are explicit CLI operations.

## Segmentation scoring and methods

Reuse Volume, voxel maps, explicit subject ID, physical RAS space identifier and
label-ontology contracts. Images and labels must have matching justified spaces;
scoring performs no registration or hidden grid conversion. If grids differ within
an established same-subject/same-world-space chain, permit one explicitly recorded
nearest-neighbor label resampling, never metric-driven registration. Reject identity,
space, ontology, units or noninteger-label ambiguity. MINC uses its actual axis
maps and scaling. Native NIfTI uses recorded nibabel affine policy and explicit
mm interpretation only when justified by publisher geometry.

BrainWeb baseline: unsupervised three-class multi-Otsu of T1 foreground above
2% of the maximum, ordered low/mid/high mapped CSF/gray/white. Extracranial false
positives remain; no ground-truth ROI, tuned thresholds or reference-derived means.
Mindboggle uses the external classifier output, not a new tissue algorithm.
Support external label ingestion with explicit role/provenance/ontology.

Report per-label Dice, Jaccard, sensitivity, specificity, absolute/signed relative
volume error; symmetric boundary distances (ASSD, maximum Hausdorff and pooled HD95),
surface Dice and boundary precision/recall at 1 and 2 mm. Boundary representation
is foreground 6-neighbor boundary voxel centers in physical coordinates, with
voxel-discretization limits stated. Both-empty overlap is undefined (absent label,
not a perfect score); one-empty overlap is zero and unavailable distances are null,
not infinity hidden in JSON. Macro summaries exclude only explicitly absent-both
cases and never omit failed/prediction-missing labels.

Controlled analytic-mask perturbations: 1-mm dilation/erosion, radial surface
shift 1 mm, localized holes, disconnected islands, seeded 1-mm boundary-field
noise, 4-mm resolution degradation, anisotropic [2,2,4]-mm sampling, and partial
volume via analytic subvoxel sampling. Keep resampling-only and segmentation
perturbations separate, recording physical scales and changed voxels.

## Topology, reconstruction and repair

Use existing extraction and triangle geometry checks, adding explicit adjacency,
incidence, components, boundary loops and orientability constraints. Euler/genus
uses only used vertices and valid connected closed orientable manifold meshes;
no genus for invalid geometry. Nonadjacent intersections, degenerates, duplicates,
triangle quality and signed/enclosed volume retain their tested scopes.

Conservative repair: exact duplicate vertices/faces, degenerate-element removal,
consistent face orientation, and at most triangular boundary loops with perimeter
<=20 mm and area <=20 mm². No global smoothing. Report before/after topology,
vertex Hausdorff displacement, area/valid-volume change, components and operations.
Accept computational repair only with valid after-geometry, <=0.25-mm vertex
movement and <=1% area change; larger/unsupported repairs are rejected and return
the original mesh. New cap patches always require anatomical review even if
computationally accepted. No watertightness-based anatomical certification.

Sample analytic sphere (R=30 mm), rotated ellipsoid (35/25/18 mm), nested spheres
(20/25/30 mm) and asymmetric radial head-like shape at voxel spacings 4/2/1 mm.
Compare binary-mask and directly sampled scalar-field isosurfaces to separate
classification/partial-volume error from interpolation. Sphere/ellipsoid volumes
and sphere areas are exact; ellipsoid/asymmetric area references use independently
evaluated high-order surface quadrature. Radial residuals are labeled as such,
not exact closest-surface distances. No monotone-convergence assertion. Full
intersection checks are bounded to <=20,000 faces; unsupported checks remain
unassessed, with no genus/certification promoted when required validation is absent.

## Continuous sources, grids and inverse crime

True sources are independently specified MRI-frame positions
[.0183,.0091,.0527],[-.0231,.0173,.0309],[.0117,-.0131,.0153] m, with moment 1e-8 A m.
Use radial-normal and 30-degree off-normal unit orientations; radial directions
are mathematical priors, not inferred human cortical normals. Reconstruction
cubic source grids have 20/15/10-mm spacing, 5<radius<=65 mm. Preserve the same
24 EEG sensors, average reference, shells 80/85/90 mm and assumed conductivities
brain/skull/scalp .3/.006/.3 S/m. Require true location >0.5 mm from every grid.

Primary continuous-source forward: independently evaluate MNE's established
layered-sphere analytical reference at each true position. Reconstruction uses
separately evaluated grid forwards. Compare same-grid inverse-crime control,
off-grid/shared analytical conductor, off-grid analytical versus triangulated BEM
(subdivision 2), boundary mismatch (inner radius +1 mm), conductivity mismatch
(skull .003 S/m) and 1-mm MRI-x registration mismatch. Explicitly state shared
physics/geometry/solver assumptions; off-grid is not fully physically independent.
No interpolation of grid lead fields is called independent evaluation.

Synthetic inverse: Tikhonov with per-grid scale ||L||F/sqrt(retained rank), lambda²
[.01,1/9,1], fixed radial and free Cartesian representations. Record actual scale,
rank/condition and noise amplification; no truth-selected regularization. Use 20
independent paired white average-referenced Gaussian sensor snapshots at expected
SNR 10 dB plus noise-free controls. Primary metrics: peak point error, nearest-grid
quantization distance, spatial energy dispersion, nearest-vertex current-norm ratio,
sensor residual and off-nearest leakage. The nearest-grid lower bound applies to
vertex-valued peaks, not centroids. No unbiased off-grid amplitude claim.

For boundary/registration interaction use a limited 2×2 design at the historical
lambda² across the three grids, paired noise draws. Report differences of differences
and approximate 95% Student-t Monte Carlo mean intervals, not additive biological
variance components. Keep numerical discretization, boundary error, noise,
orientation mismatch, registration and regularization labels distinct.

Conditional realistic example: MNE sample participant, same computationally
checked FLASH BEM and retained EEG as M8/M9. Independently position dipoles at
MRI [-.04,-.02,.05] and [.02,0,.01] m, checking inside geometry and noncoincidence.
Reconstruct on participant white ico2/ico3 grids, fixed normal/free orientations,
lambda²1/9, MNE depth .8 and independent training covariance. Normal direction is
borrowed explicitly from the nearest cortical vertex; add 30-degree off-normal
truth. This is shared-conductor conditional BEM evaluation, not independent
anatomical truth or a validated cortical off-surface orientation model. Report
failures rather than moving truth onto an accepted vertex. No real conductor
boundary perturbation is promoted as biological ground truth.

## Reproducibility and acceptance

Seed 42, named independent streams and paired draws within comparisons. Caches
bind locations, sensors, conductor, transforms, orientation, code/software and
checksum; inverse settings cannot silently reuse incompatible kernels. Save input
SHA256, formats, geometry, label definitions, truth, outputs, failures, timing/RSS
and source-tree/Git/environment identity. Ten requested figure categories have
numeric companions and explicit analytic/simulated/manual/derived references.
Normal CI is offline; real references and BEM integrations are opt-in. Preserve all
495 tests and old reports. Verify new numerical oracles, actual reference files,
all six workflows, figures and static/dependency checks; mark incomplete real-data
criteria if necessary. Target 0.10.0, local commit only; no Milestone 11 work.
