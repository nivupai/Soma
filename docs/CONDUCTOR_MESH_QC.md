# M32 conductor QC and evidence limits

One curated MNE sample educational anatomy has T1 plus provided FLASH-derived
inner-skull, outer-skull and outer-skin boundaries, provided FreeSurfer aseg, measured
59-channel EEG geometry and a supplied head→MRI transform. This workflow actually
loads the MRI and segmentation, validates their common grid, reconstructs explicit
voxel/scanner-RAS/surface-RAS/head frame maps, discretizes the provided surfaces,
selects MRI-GM source regions, audits topology and computes forward/inverse operators.
FreeSurfer extraction tools are absent: fresh segmentation or boundary extraction is
not claimed. The transform is curated dataset provenance; authenticated identity and
independent manual fiducial truth remain unavailable.

Three BEM mesh levels have 162/642/2562 vertices and 320/1280/5120 faces **per boundary**.
All nine attempted surfaces pass: closed single component, zero boundary/nonmanifold
edges or vertices, zero duplicate/degenerate faces, consistent outward winding,
positive enclosed volume, zero detected self-intersections and correct nesting.
The reused geometric intersection implementation and engineering thresholds are QC,
not proof against all geometric defects or anatomical mislabeling. Exact scalar QC
is in `aggregate.json`; no participant vertices, faces or enclosed volumes are public.
No tetrahedra are generated; positive tetrahedral volumes are therefore not applicable.

Minimum triangle quality across nine surfaces: 0.742278. Minimum interface separation: 2.775178 mm.


At primary level 3, maximum measured-electrode/scalp distance is 5.669 mm (frozen
limit 30 mm). Distances are geometric fit discrepancies, not target registration
error. Source margin is at least 9.885 mm across executed operators, above the frozen
5 mm minimum; no sources or electrodes are dropped. Transform pairing residual is
zero at the recorded precision. Scanner-coordinate oracle error is 2.78e-17 m;
voxel roundtrip error 5.69e-14 voxels. Tests use an independently specified MGH
voxel-center oracle, not only an inverse of Soma's own functions.

Conductivity is scalp/skull/brain .3/.006/.3 S/m. Brain homogenizes CSF. There is no
separate CSF interface, independent skull/scalp truth or measured conductivity.
Readiness: **0 VALIDATED_ANATOMY, 1 QC_ONLY_ANATOMY**, and 23 tissue-reference cases
**NOT_READY_FOR_FORWARD_MODEL** as complete conductors. Failed reference evaluations
cannot silently downgrade to QC-only. NOT_READY cases do not enter the forward worker.

Existing four-material FEM and three-compartment human BEM are **NOT_COMPARABLE**.
No geometrically incompatible BEM/FEM difference is reported as solver error. The
supported same-surface comparison is MNE/OpenMEEG BEM, not anatomical validation.

A descriptive QC supplement (`decimation-displacement.csv`) measures each decimated
boundary against the provided full FLASH surface. Bidirectional vertex-to-triangle
sample means, pooled-sample HD95 and maxima are explicitly sampling diagnostics,
not area-integrated ASSD or independent anatomical error. Added after the primary
replay, with no new acceptance threshold or change to frozen numerical results.

At primary level 3, largest sampled displacement over three boundaries is 3.887575 mm. Level 4 reproduces the provided native boundaries to <3e-14 mm sampled distance; this does not validate those boundaries against MRI truth.
