# External anatomical and computational references

SCI Head Model is the single female participant computational reference distributed
by the University of Utah SCI Institute; acquisitions were at EGI/University of
Oregon. Official entry: https://sci.utah.edu/sci-head-model/ . Citation: Warner,
Tate, Burton and Johnson (2019), DOI 10.1101/552190. The institutional page requests
attribution and NIH P41 GM103545/R24 GM136986 acknowledgment. It does not establish
an SPDX license for every file; no raw images are redistributed in Git.

Downloaded official Segmentation.zip, T1.zip, acquisition-report and simulation
network archives. Extraction selects the corrected T1, segmentation, READMEs,
SCIRun networks and one DICOM metadata slice; it does not expand the full DICOM
series or download DWI/fMRI/EEG and multi-million-element tetrahedral meshes.
Archive sizes/checksums and native NRRD geometry are saved by `references inspect`.
No external segmentation is promoted into anatomical truth.

Actual T1 and labels are 208×256×256. T1 is float with LPS header; labels are uint8
with codes **1–8**, not 0–7. The segmentation names `3D-right-handed`, which does
not identify anatomical axis directions, and neither NRRD declares space units.
A selected raw DICOM slice supports 1 mm acquisition spacing for the T1, but it
does not prove the segmentation's anatomical orientation. Native slices are shown
separately, never overlaid as if registration had been verified.

The archive README calls the labels an eight-layer Seg3D segmentation but does not
state expert review, annotation repeatability, or the ID-to-tissue mapping. The
SCIRun lead-field network contains a 0-indexed conductivity array, whereas stored
labels run 1–8. No index shift or assignment is inferred. The array is retained as
network metadata, with its origin, not applied to a new conductor. The paper's
indexed search excerpt and network also differ in skin/skull numeric values;
users must resolve the actual mapping and intended model before physical use.
The parser validates scalar payload dimensions, gzip length, type, finiteness and
bounded allocation. Conversion to Volume refuses generic handedness and unknown
units unless external evidence and explicit overrides are provided.

The published Cleaver model is tetrahedral FEM, with 15.7/60.2 million elements.
That representation cannot certify inner-skull/outer-skull/scalp triangular BEM.
No eight-to-three-tissue aggregation was attempted. External BEM readiness stays
**INDETERMINATE** for frame/units, ontology, interface correspondence, electrode
chain and independent boundary evidence. Native component counts are topology
diagnostics, not physiological validation. Existing BEM readiness is exercised on
known synthetic shells, which must not be substituted for external anatomy.

MRBrainS13 (https://mrbrains13.isi.uu.nl/) is an authorized-local-only adapter.
IBSR v2.0 release 2316 (https://www.nitrc.org/frs/shownotes.php?release_id=2316)
was prespecified as the accessible tissue substitute. The selected download
https://www.nitrc.org/frs/download.php/5731/IBSR_V2.0_nifti_stripped.tgz currently
redirects to NITRC login. No registration, private access or mirror bypass was
attempted. Its public release notes include a public-domain statement alongside
the original CMA use notice; the project lists non-commercial use. Record these
conditions rather than assuming a blanket CC license. Raw redistribution is not
part of this milestone. Until authorized files are supplied, per-subject tissue
and multi-subject population acceptance criteria remain incomplete.
