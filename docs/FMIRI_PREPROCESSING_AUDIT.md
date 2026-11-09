# Auditing external fMRI preprocessing

Soma0.14 imports fMRIPrep outputs; it does not implement motion, distortion,
slice-timing correction or normalization. Normal M14 human fits are gated by an
explicit preprocessing audit. The earlier SPM raw educational exception is not
used to populate motor-task reliability results.

PreprocessingBundle binds raw/derivative roots, subject/session/task/run, space,
BOLD, mask, confound TSV/JSON, T1w, transform evidence and available HTML reports.
PyBIDS performs explicit selection; missing or ambiguous assets fail. The legacy
ds000114 BIDS1.0.0rc2 description is indexed with validation disabled and never
called compliant with the current specification. Source dataset URL/DOI, BIDS URI
links, exact raw image relationship and checksums are inspected. fMRIPrep
GeneratedBy/version is required; a filename is insufficient evidence.

Numerical checks reuse strict Soma NIfTI geometry: coded qform/sform, explicit
mm/sec, positive finite TR, source/derivative counts, all finite BOLD samples,
confound rows, binary mask grid and explicit spatial reference. Changing sample
count is unsupported without a new explicit temporal-remapping adapter; it cannot
silently shift events. An audited slice-time reference must be declared rather
than guessed from fMRIPrep naming. T1 sources, transform source/reference grids,
controlled landmark evidence and reviewed QC reports are retained.

ITK affine/composite/nonlinear transforms are read through SimpleITK with explicit
from/to space, subject, point direction and reference/source images. Soma RAS m
points cross to ITK LPS mm through the existing geometry transform. Filename
from/to labels are checked but do not establish point convention. Controlled
landmarks quantify numerical error; an analytic rotation+displacement composite
independently checks composition order. Nonlinear objects remain nonlinear,
GetInverse is queried rather than assumed. Linear transforms also pass Soma
rank/conditioning checks, since a library inverse call can succeed numerically
for a singular projection. No nonlinear warp is coerced into a matrix.
ROI label resampling continues to require a supported explicit chain and nearest
interpolation. General nonlinear ROI/image resampling is not added here.

PASS means the declared metadata, numerical geometry, landmark and reviewed
heuristic criteria are satisfied. Independent anatomical validity remains
INDETERMINATE. Correlation/normalized RMSE on a declared common grid are heuristic;
they do not establish anatomy or justify registration by themselves. Supplied
external evidence must be independently audited; Soma cannot prove a caller's
claim that a review or landmark set is anatomically correct.

Audit identity binds all input files, inherited acquisition/events, source code,
T1 sources, transforms, grids, evidence and QC. load_audited_run rechecks eligibility
and identity; stale inputs cannot reuse an earlier PASS. Cohort gates require a
successful current-source pilot, intact report hashes and unchanged input hashes.
No original or preprocessed files are repaired or overwritten.

The external fMRIPrep adapter builds an exact single-participant command and
records versions/parameters when explicitly executed. It installs/pulls nothing.
Execution requires a preinstalled executable, declared complete local resources
and an explicit offline launcher; network enforcement is the caller's external
launcher responsibility. It is not automatically invoked. In this environment
fMRIPrep is absent and Docker's daemon is unavailable, so no preprocessing ran.

References: [fMRIPrep outputs](https://fmriprep.org/en/stable/outputs.html),
[SimpleITK transform conventions](https://github.com/SimpleITK/SimpleITK/blob/main/docs/source/fundamentalConcepts.rst).
