# Independent label benchmarks

`benchmarks.segmentation.LabelVolume` wraps the existing Volume with explicit
subject, physical world-space identifier, target ontology and provenance. Equal
array shapes are insufficient: different subjects, spaces, label meanings or voxel
maps fail. Scoring never registers or resamples. The workflow's one permitted
explicit label reindexing is separately recorded with nearest-neighbor semantics.

Per-label metrics are Dice, Jaccard, sensitivity, specificity, reference/predicted
volume in mm³, absolute volume error and signed/absolute relative volume error.
All non-target voxels still participate as negatives; missing predicted targets
are not silently dropped. Both-empty overlap is undefined and reported as an
absent label, excluded from a descriptive macro mean. One-empty overlap is zero;
unavailable boundary distances are null, not hidden infinity or perfect accuracy.

Boundary measurements use exposed voxel-face **centers** transformed to physical
millimetres, weighted by their physical parallelogram areas. Surface Dice at
1/2 mm sums matched areas from both surfaces; precision/recall use their respective
areas. ASSD is pooled area-weighted symmetric distance; HD95 is its pooled weighted
empirical percentile, and Hausdorff is the maximum sampled distance. These are
finite surfel approximations, not exact continuous tissue-boundary geometry.
The rectangular-voxel oracle independently verifies physical area and distances;
rotations/storage reflections are handled by the existing voxel affine.

## BrainWeb

The actual original-normal 1-mm T1, noise0/RF0 MINC image is evaluated against the
provided discrete dominant-tissue reference. The reference class counts match
McGill's published table. Fuzzy memberships are documented as available but were
not downloaded or substituted for hard tissue truth. The simulated image was
produced from a fuzzy anatomical model, so partial-volume differences are expected.

The prespecified global three-class Multi-Otsu T1 baseline uses foreground above
2% maximum and maps ordered classes CSF/gray/white. It uses no reference-derived
ROI, supervised tissue means or outcome-tuned thresholds. Extracranial false
positives remain. Dice is **0.34542 / 0.70317 / 0.75710**, macro **0.60190**.
Mean ASSD across three tissues is 6.692 mm; mean HD95 28.162 mm. Mean surface Dice
is 0.56683 at 1 mm and 0.59520 at 2 mm. These unfavorable values describe the
limited baseline, not a verified clinical segmentation method.

## Mindboggle

The actual NKI-RS-22-11 native T1/manual DKT31 reference is compared with the
publisher's separate JTAtlas40+aseg classifier output after an exact, explicitly
recorded native-world reindex/crop. All **62 cortical target labels** are scored;
none is absent in both. Original IDs and raw files remain unchanged. Macro Dice
is **0.92075**, mean ASSD **0.33788 mm**, mean HD95 **2.21242 mm**; mean surface
Dice is **0.92061 / 0.94568** at 1/2 mm. Labels are not independent participants,
so no population confidence interval is manufactured from these 62 regions.

This is agreement against manually edited cortical parcellations from one selected
subject. It is not human CSF/gray/white ground truth, an independent prospective
population test or skull/scalp validation. Shared historical annotation/classifier
lineage remains a limitation. Native/MNI assets and cortical VTK are preserved;
unverified surface-frame chains are explicitly unassessed. See
[M10 acquisition provenance](MILESTONE10_DATA_PROVENANCE.md) for licenses, original
formats, unit overrides, exact classifier alignment and development corrections.

The generic Volume/LabelVolume ingestion APIs also accept independently supplied
external predictions. Roles, ontology, modality, preprocessing, parameters and
software/input hashes must be declared. No comprehensive new segmentation backend
or deep-learning model was added. Controlled analytic mask defects are reported
separately and do not count as independent segmentation-method validation.
