# M32 architecture and anatomical evidence gaps

M31 is integrated at 3aff2339a6d8133815eb1cd9a4fb1d8e134587f8, with all 14
post-merge jobs passing. Native Gmsh still reports scientific FAIL under the
unchanged characterized-failure policy. Local main was synchronized before M32.

Reuse: M7 Volume/NIfTI, explicit metre transforms and RAS/LPS maps; M8/M9 matched
MNE sample assets, digitization, FLASH boundaries, coregistration, geometric
surface QC and participant BEM; M10–M12 independent tissue prediction/scoring and
reference ontology adapters; M12 private MRI workflow/cache; M26–M30 numerical
BEM/FEM controls and M31 Gaussian moment priors. These remain distinct evidence
sources. The user roadmap's stage names differ from historical report titles;
actual M12 processing results and current code determine this integration.

Missing pieces are an explicit scanner-RAS/surface-RAS transform chain; a
non-spherical MRI-domain quadrature adapter for M31; evidence-level readiness
rather than a geometric PASS implying anatomy; privacy-safe aggregate export;
and a locally authorized, unbundled MRI showcase. No new segmentation network,
weights, broad MRI framework or M33 factorial is introduced.

IBSR and MRBrainS support brain-tissue scoring, not skull/scalp truth. Historical
macro Dice 0.587/0.456 is poor and remains historical. Their known outcomes cannot
serve as a fresh holdout. MNE sample has participant-matched T1/FLASH derivatives,
measured EEG geometry and a supplied head/MRI transform, but no independent manual
full-conductor boundaries or true source locations. Supplied FreeSurfer aseg is
an automated reconstruction, not independent segmentation ground truth.

The supported full-head path therefore consumes existing MRI-derived FLASH
boundaries, audits and discretizes them, and computes conditional research BEM.
FreeSurfer reconstruction executables are absent; fresh watershed/FLASH extraction
is not claimed. A three-compartment brain/skull/scalp conductor homogenizes brain
and CSF; it is not the synthetic four-material model. The existing four-material
FEM adapter cannot provide a physically matched three-compartment human comparison
without new independently validated assembly/meshing. M32 reports that incompatibility
and compares supported MNE/OpenMEEG BEM on identical boundaries instead.

Source weights come from actual eligible GM voxel measure, not spherical M31
weights. A conservative anatomy-derived inscribed region guarantees source-domain
containment. It limits cortical coverage and is explicitly reported. Source activity
is simulated within real MRI-derived geometry; no human localization accuracy is
inferred. Actual MRI, reference overlays, surfaces, coordinates and lead fields
remain local and ignored. Public assets contain aggregate metrics only.
