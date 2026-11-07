# Recorded protocol amendment: inspected resource provenance

This amendment corrects assumptions after dataset inspection/development trials;
it does not rewrite the original frozen protocol or claim preregistration of an
observed outcome. The original file hashes remain intact.

The official MNE sample archive (OSF version 6, MD5 e8f30c4516abdc12a0c08e6bae57409c)
contains default bem/inner_skull.surf, outer_skull.surf and outer_skin.surf symlinks
to bem/flash/*.surf. Each default/FLASH pair has identical SHA256. The initial
protocol called the distributed default products watershed-derived, following
the general dataset description. That product attribution was incorrect for
this archive. Permit and accurately label the supplied participant FLASH-derived
boundaries. No boundary is selected by source-recovery accuracy and no vertices
are moved or repaired. The duplicate FLASH paths are not an independent anatomical
sensitivity comparison. Optional watershed generation remains explicit and requires
FreeSurfer; it is not substituted into the primary analysis.

The archive has no participant MRI fiducial file. MNI-derived estimates are allowed
only as an explicitly derived initialization/reference-implementation comparison.
The predeclared 20-mm fiducial truth gate cannot be evaluated against those
estimated targets and remains INDETERMINATE. The primary distributed transform
is retained, rather than replaced by the fiducial-only or ICP fit with smallest
residual. Source-space identity and headshape/electrode/scalp geometry are checked,
but do not supply independent anatomical registration truth.

An initial implementation introduced an unregistered >3-mm inward-electrode
sanity rejection and encountered EEG 026 about 3.24 mm inside the ico3 scalp.
Inspection of MNE's documented EEG forward behavior shows that it evaluates
EEG using nearest-scalp barycentric projection. Correct that implementation
assumption: retain all measured good-channel coordinates, record signed/absolute
surface discrepancies and explicitly use MNE's standard projection. Do not
pretend the projected contacts were newly digitized or prove correct anatomy.
Keep an explicit gross >30-mm discrepancy rejection. No protocol surface/nesting
threshold, conductivity, regularization or primary transform is relaxed.

Development already included surface QC, a conditional 59×1239 EEG forward and
an illustrative reconstruction before these provenance corrections. Those runs
are exploratory. Final reports must be rerun with this amendment receipt and
accurate product/projection/fiducial provenance. Overall unsupported anatomical
certification remains INDETERMINATE. The amendment is a factual resource/adapter
clarification, not anatomical certification or a recovery-tuned model choice.
