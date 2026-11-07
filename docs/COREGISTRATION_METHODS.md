# Participant coregistration methods

The frozen [protocol](INDIVIDUAL_HEAD_MODEL_PROTOCOL.md) and disclosed
[post-development amendment](INDIVIDUAL_HEAD_MODEL_AMENDMENT.md) govern this study.
HEAD and FreeSurfer MRI surface RAS are distinct right-handed frames. Numerical
positions and translations use metres. Disk FreeSurfer surfaces use millimetres;
MNE converts them. MRI overlays use the MGH `vox2ras_tkr` map, not scanner RAS.
The sample adapter records both voxel maps, dimensions and voxel spacing.

`geometry.coregistration.rigid_align` minimizes Σ wᵢ‖Rxᵢ+t−yᵢ‖² using weighted
centering and SVD of the cross covariance, with det(R)=+1. It requires at least
three positively weighted noncollinear correspondences. Full-rank mirrored sets
are rejected. Three planar fiducials determine a proper rotation but cannot
independently establish chirality. Named LPA/nasion/RPA matching reorders by name;
missing, repeated or incompatible names fail. Optional deterministic RANSAC uses
seeded triples and refits weighted inliers. Rejection is recorded, never hidden.
MNE `fit_matched_points` is an established numerical comparison; known synthetic
transforms supply the independent recovery oracle.

`icp_align` accepts only explicitly identified digitized or synthetic headshape
points. Each step matches nearest scalp **vertices**, retains the nearest 90%
within 30 mm, and fits a proper rigid update. Maximum 30 iterations, stopping
at 1e-7 m change. This objective differs from exact point-to-triangle distance;
both are labeled. Final distance reporting uses a conservative KD-tree broad
phase and exact point-to-triangle features, without a dense all-pairs matrix.
Electrodes, HPI and cardinal points are not silently reclassified as headshape.
Transforms support checked composition, inversion and MNE FIF serialization.

For the real participant, retain the distributed head→MRI transform. Three
measured head cardinal points exist; manually measured MRI fiducials do not.
MNE's `get_mni_fiducials` derives initialization targets through the participant's
Talairach mapping. Their residuals are **proxy discrepancies**, not anatomical
registration errors. The 20-mm truth gate therefore remains INDETERMINATE.
The SVD and ICP alternatives are comparisons, not replacements chosen by source
recovery. Low fit error cannot establish correspondence or anatomy.

Measurement perturbations use per-coordinate Gaussian SD 1/3/5 mm for fiducials
and electrodes, 1/3 mm for headshape. Fiducials/headshape are actually refitted.
The real sweep includes unperturbed refit branches: compare against these to
separate measurement noise from changing the fitting method. Direct translation
is along MRI x (1/3/5 mm); rotation is about the MRI-origin z axis (1/3/5 degrees).
Only synthetic experiments report true transform error. A spherical scalp has
rotation ambiguity: the synthetic headshape demonstration starts at truth and
cannot certify global ICP identifiability. An irregular-cloud regression checks
recovery with an independent known transform.

See [executed results](INDIVIDUAL_SOURCE_VALIDATION.md) for numerical residuals.
The optional MEG demonstration preserves its acquired device→head matrix.
Its maximum orthogonality defect is about 5.79e-7 and determinant 1.000000703;
it passes a separately reported 1e-6 near-rigid acquisition check. It is not
rounded or orthogonalized. The generic exact-rigid API retains its 5e-7 check.

Primary references: [MNE coregistration tutorial](https://mne.tools/stable/auto_tutorials/forward/25_automated_coreg.html),
[MNE coordinate frames](https://mne.tools/stable/auto_tutorials/forward/20_source_alignment.html).
