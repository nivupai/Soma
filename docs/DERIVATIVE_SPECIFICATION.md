# Supported anatomical derivatives

Target schema: BIDS1.11.2. Dataset description identifies DatasetType=derivative,
GeneratedBy Soma/version and SourceDatasets URL. Genuine BIDS sources use a
DatasetLinks source entry and BIDS Sources URIs; non-BIDS sources retain file URIs
and explicit legacy/standalone origin. These are local/private relationships,
not permission to publish source metadata. Original sources are never modified.

Supported products under sub-*/[ses-*]/anat:

* desc-preproc_T1w.nii.gz + JSON: explicit SkullStripped boolean and spatial/source
  relationships, processing/backend configuration and native geometry lineage.
* desc-multiotsu_dseg.nii.gz (or desc-segmentation for imported/external output),
  JSON and matching TSV: custom CSF1/GM2/WM3 indices with explicit BIDS mappings
  CSF3/GM1/WM2. Soma indices do not silently masquerade as BIDS default tissue IDs.
* desc-foreground_mask.nii.gz + JSON when requested, Type=ROI: a foreground
  candidate/imported mask, not certified brain extraction.

Source acquisition/run/reconstruction entities and selected session are retained.
SpatialReference=orig describes the native image coordinate space, including
explicit voxel-grid resampling in that space, not MNI registration. Transform
receipts retain source/destination RAS frame, metre matrix, reference grid,
reference-to-source pull direction, interpolation and provenance. Native geometry
is saved separately. Nonlinear transforms cannot be forced into an affine reader.

Atomic exclusive subject publication avoids incomplete anatomical folders. Existing
products are never overwritten: identical completed resume verifies all recorded
hashes; partial publication recovery compares image contents, geometry, provenance
and tissue LUT. Different runs/configurations require new output/report roots.
Only one selected T1 acquisition per subject/session/output is supported; use a
new derivative dataset for another selection. No automatic multi-scan averaging.

Stage journals, QC JSON, mesh arrays, figures and benchmark tables are custom Soma
reports in a separate report tree. They are not advertised as standardized BIDS
suffixes. `validate_derivatives` performs structural/entity/metadata checks through
PyBIDS plus the optional full official schema validator. Filename checks alone are
insufficient. Compliance is claimed only for actually validated supported outputs,
with exact schema/tool and warnings retained. Missing validator means INDETERMINATE,
not compliance. No anatomical or clinical certification follows from schema PASS.

## Milestone 13 addendum: functional analysis products

fmri.outputs reuses the private-output guard and official offline validator.
Supported functional analysis masks use sub/ses/task/run entities, desc-analysis,
Type ROI, SpatialReference orig, exact internal space identity and BIDS source URI
relationships. They are heuristic analysis domains, not certified brain extraction.
Dataset description records Soma version, source dataset links and derivative type.

BIDS1.11.2 supplies no general statistical-map suffix here. Effect/variance/t/z,
explicit two-sided p/BH q/rejection maps and contrast metadata stay in a separate
Soma custom-report directory. They retain source identity, affine, native effect
units, model/contrast/tail/DOF and correction family, without pretending a custom
statistics suffix passed standardized BIDS validation. The unused Nilearn upper-
tail p output is not exported under the two-sided policy. No unrelated derivatives
are overwritten. See [M13 results](MILESTONE13_RESULTS.md).
