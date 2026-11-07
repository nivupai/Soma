# Individual head-model protocol, recorded before real analysis

Baseline Soma 0.7.0, commit 8d54270. The primary question is how geometry,
coregistration and assumed conductivity errors change EEG predictions and inverse
reconstruction. This is a methodological sensitivity study, not clinical or
anatomical certification. The corresponding YAML files and freeze receipt bind
these decisions before analysis. No Milestone 9 work is authorized here.

## Dataset and identity

Primary: the official MNE sample audiovisual subject `sample`, with matching
MEG/EEG, digitized electrode/cardinal/headshape points, subject MRI, distributed
FreeSurfer white surfaces, watershed conductor boundaries and sample head↔MRI
transform. Never select `morph` or `fsaverage` as participant anatomy. Source
paths, file checksums, source-space subject IDs, digitization kinds and coordinate
constants must agree. Dataset documentation identifies the correspondence; it
is not an independently authenticated clinical subject identity.

Fetch only selected resources when supported. MNE's public sample fetcher exposes
a full compressed archive rather than per-file retrieval; explicitly requested
fetching may therefore obtain that archive. It must not set persistent user
configuration. Inspect and hash only required assets for the study. The sample
is supplied for learning MNE, not evaluation of the recording hardware/MRI system.
Record the distributed license and official resource/version/hash. Secondary
OpenNeuro ds000117: metadata discovery and optional exact selected-subject files,
never an automatic dataset-wide download; use the current BIDS dataset's own
license/subject map, not a different historical release's terms.

## Sensor and coregistration requirements

Primary EEG needs finite individually digitized retained EEG channels, three
identified cardinal landmarks and explicit head coordinates. Dataset-marked bads
are excluded; EEG-only analysis removes unrelated MEG SSP and applies average
reference on the retained EEG set. Digitized headshape EXTRA points are separate
from EEG electrode locations and HPI coils. MEG-only fallback, if needed, must be
separately labeled with device→head geometry, never fabricated EEG electrodes.

Use the distributed participant head→MRI transform as the primary model; compare
with independent weighted SVD fiducial registration and optional robust/headshape
ICP. Do not replace it with an outcome-selected fit. Cardials are ordered LPA,
nasion, RPA by identifiers. Reject too few/collinear correspondences, reflections,
nonfinite coordinates and incompatible frames/units. Planar noncollinear three
fiducials are sufficient for proper rigid fitting. Report per-landmark fit,
headshape and electrode-to-surface distances separately from known synthetic
transform error. A fit residual is not real anatomical ground truth. A maximum
20-mm individual fiducial residual is an exploratory gate, not an accuracy claim.

## Surfaces and BEM

Use distributed subject watershed surfaces; no new production segmentation is
invented. Optional MNE watershed generation requires explicit invocation and
available licensed FreeSurfer/MRI products; never silently repair failed surfaces.
Validate actual solver surfaces from MNE ico3 preparation with Soma topology,
vertex links, oriented edges, nonadjacent self-intersections, pairwise triangle
separation and solid-angle containment. Require one connected closed oriented
boundary per layer, no degenerates/duplicates/nonmanifoldness, positive signed
volume under checked geometry, triangle quality >=0.01 and minimum boundary
clearance 0.1 mm at tolerance 1e-8 m. Report native mesh inspection separately
from the mesh actually sent to the solver. Unsupported geometric/anatomical
conditions are INDETERMINATE. No generic topology check establishes anatomical
boundary correctness. Preserve the failed SPM foreground result from Milestone 7.

Readiness has PASS/FAIL/INDETERMINATE per topology, geometry, anatomical evidence,
coordinate consistency, measured sensor compatibility and numerical suitability.
A required failure prevents use. An unsupported required check prevents overall
PASS. A model with passed computational checks but unavailable anatomical truth
can only be an explicitly conditional research computation, not a fully certified
individualized model. If coregistration or conductor geometry fails, stop that
real workflow and retain verified synthetic/numerical work; do not substitute a
sphere or template and call it individualized.

Delegate conductor solutions/forwards to MNE. Baseline three-shell conductivities
are scalp/skull/brain 0.3/0.006/0.3 S/m. These are assumptions, not measurements.
Recompute the conductor and forward for every alternative conductivity, with
fingerprinted caches. Source space is participant white-surface ico3, min distance
5 mm, fixed signed cortical normals with use_cps=False. Keep the native free
surface-oriented forward for MNE depth weighting. No entrywise matrix comparison
without matching channel order, hemisphere/vertex IDs and physical orientation.

## Synthetic truth and sensitivities

Deterministic nested spherical shells, known fiducials, electrodes and sources
supply geometric and rigid-transform truth. Check an independent analytical MNE
layered sphere against triangulated spherical BEMs at two discretizations;
record discretization error separately from registration error. Include wrong
landmark correspondences, outliers, crossings and nonmanifold boundaries.

The source-uncertainty YAML prespecifies 1/3/5-mm translation/electrode/fiducial
scales, 1/3/5-degree rotation, 1/3-mm headshape noise, and separate scalp/skull/brain
conductivity alternatives. Rigid perturbations are applied about the defined MRI
origin and their realized displacement is reported. Measurement perturbations
actually alter inputs and refit when appropriate. Preserve source/sensor IDs.
Central differences use three step scales for translation, rotation, electrode
and skull-conductivity derivatives; report relative derivative changes, not an
assumed convergence rate. Test local Jacobian covariance predictions against
20 seeded small-translation Monte Carlo realizations on a validated small model.
Do not extrapolate local linear propagation to the larger sweeps.

Generate independent sensor-noise training samples; ground truth is used only to
simulate currents/control SNR/evaluate error. Primary inverse is fixed beforehand:
MNE depth 0.8, lambda2=1/9, signed normals, nave=1. The educational SVD solver is
restricted to small synthetic numerical controls. No truth-selected regularization
or oracle winner is promoted. Record peak error, amplitude bias, dispersion,
leakage, residual and variance even when recovery is poor.

## Matched-subject signal example

Use cached sample_audvis_filt-0-40_raw.fif and actual stimulus codes: auditory left
1/right 2, visual left 3/right 4. No PhysioNet motor-imagery labels. Extract
[-0.2,0.5] s with [-0.2,0] baseline and 150-uV peak-to-peak rejection, at most the
first 12 accepted trials per condition. Estimate pre-stimulus background covariance
with fixed 0.1 shrinkage. It includes background neural activity and artifacts,
not pure instrument noise. Reconstruct with the same nave=1 inverse and record
50–200-ms phase-locked response maps plus trialwise versus evoked band-power
comparison. Do not use evoked power as the sole statement about induced activity.
No real-source truth, anatomical activation accuracy or population inference is
available from this single illustrative participant.

## Provenance, budget and missingness

Seed 42, one MNE/BLAS worker. Target <=8 GiB extra assets/cache and <=2 GiB active
memory, sequential conductor solutions, no dense source-resolution or all-pairs
surface distances. Cache only physical model stages whose fingerprints match
assets, channels, coordinates, source identities, transform, conductivity, solver,
code and versions; unrelated inverse settings do not invalidate BEM caches.
Measure stage wall/CPU time and process peak RSS. Normal CI uses small offline
fixtures, never downloads anatomy. Large sample integration is explicit.

Freeze configurations before real experiments. Persist all settings, versions,
checksums, transform matrices, source/sensor IDs, diagnostics and figure arrays.
Unavailable modalities/assets/alternative anatomical products remain explicit
missingness; unsupported certification remains INDETERMINATE. Sensitivity is not
estimated individual conductivity or calibrated population anatomical uncertainty.
