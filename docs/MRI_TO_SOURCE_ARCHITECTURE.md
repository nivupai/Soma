# MRI-to-source architectural boundary

Milestone 7 supplies physical image geometry and candidate surfaces to complement
the working Milestone 6 MNE forward/inverse pipeline. The existing fsaverage
pipeline is unchanged. No unrelated participant MRI is substituted into EEGBCI.

`AnatomicalModel` communicates explicit subject identity, original MRI provenance,
RAS-m image geometry, three ordered candidate surfaces and a justified rigid
NIfTI-RAS→MNE-MRI transform. The transform and provenance are mandatory. Surface
frames must match the MRI physical convention. A missing or unjustified frame
conversion cannot be replaced by an identity matrix for a real participant.
Synthetic tests explicitly define coincident frames by construction.

NIfTI scanner/aligned RAS coordinates and MNE/FreeSurfer surface (tkregister) MRI
coordinates are not automatically identical. When valid corresponding anatomical
headers exist, a future adapter can derive scanner-RAS↔surface-RAS through their
respective voxel maps, carefully converting mm to m. An affine from an arbitrary
NIfTI is not enough to invent that relationship. See MNE's
[source alignment and coordinate frames](https://mne.tools/stable/auto_tutorials/forward/20_source_alignment.html).

Candidate export applies the explicit RAS→MNE-MRI chain and supplies geometry
with MNE surface IDs 1/3/4 and coordinate-frame constant 5, using metre-valued
vertices and triangle identities. The receipt includes original MRI geometry,
source metadata, the transform matrix, subject and geometric validation state.
These are candidate dictionaries for a future established MNE surface-preparation/
conductor workflow; this method does not construct or validate a BEM solution.
Conductivity assignment and anatomically defensible boundary evidence remain
separate requirements. No new BEM solver is introduced.

An EEG alignment check independently requires matching subject identity,
a proper rigid head→participant-MRI transform and explicit provenance. It returns
the head→MRI and composed head→NIfTI-RAS chain. Template MRI is a distinct frame
and cannot pass as participant MRI. Supplying a provenance string is an interface
requirement, not proof that the claimed scientific alignment is accurate.
Coregistration uncertainty, measured sensor positions and anatomical inspection
must establish accuracy in a future validated workflow.

The exported candidate report continues to mark individual forward validation
false. The real SPM image has no corresponding EEGBCI sensor recording or measured
head-to-MRI coregistration; no such pairing is fabricated. Only synthetic geometries
exercise the bridge. Real foreground topology failures are retained, so the API
does not call an arbitrary threshold mask brain/inner skull, outer skull or scalp
merely because a caller supplies those names.

The regression suite runs existing geometry, MNE covariance and fixed/free inverse
checks unchanged. A fresh subject-1 trial-wise MNE/dSPM source demonstration also
confirms that MRI additions did not replace the validated fsaverage anatomy.

## Implemented participant assets (Milestone 8)

The candidate-mask pathway above still cannot certify anatomy or pair SPM with
unrelated EEG. A separate `IndividualModel` now accepts curated corresponding
MNE sample MRI/EEG assets. Its identity/provenance includes MGH voxel dimensions,
scanner-RAS and tkregister-RAS maps, three named conductor asset hashes and QC,
measured sensor locations/projectors, head→MRI transform, uncertainty scope,
source configuration, and physical BEM/forward cache receipts. MRI plots use the
tkregister map with explicit mm→m conversion. No arbitrary NIfTI affine is used
as a substitute. Contracts reject subject/frame/ordering mismatches and template
identities; final forward reports retain source orientation and inverse provenance.

The source pathway runs only after computational checks pass; independent
anatomical evidence remains unavailable, so overall readiness is INDETERMINATE.
This conditional participant research pathway does not upgrade generic M7 masks
or the failed SPM foreground to anatomical conductor boundaries.

## Reliability evidence (Milestone 9)

A subject contract is necessary but does not prove anatomy. `reliability.evidence`
now attaches explicit evidence categories/check definitions to provenance, transform
chains, conductor topology/nesting/orientation/intersections, sensor geometry and
surface-to-volume comparisons. Independent tissue and MRI-fiducial truth remain
missing. The resulting anatomical state is INDETERMINATE even when computational
geometry passes. No uncertain mask is upgraded by an arbitrary score.
