# Source-modeling protocol — Milestone 6

Seal this specification before real-data source analysis. Baseline is v0.5.0,
commit 6bc9999. This is a numerical/methodological demonstration, not anatomically
validated inference. No reconstructed map is claimed to reveal the true physical
generators, individual anatomy or individualized motor-cortex activation.

## Geometry and forward assumptions

Use MNE fsaverage assets fetched only by an explicit option into data/anatomy.
No ordinary test downloads anatomy. Use the supported fsaverage head↔MRI rigid
transform and anatomically compatible fsaverage_1005 montage after EEGBCI label
normalization. Record original MRI-space template positions and transformed head
positions, matching channel identities, units and transform direction. These are
template electrodes, not digitized positions for a PhysioNet participant.

Use the precomputed three-shell fsaverage BEM solution; record its actual shell
conductivities and hashes rather than changing a stored scalar and pretending
to recompute physics. MNE computes EEG forward operators. Primary white-surface
source space is ico3, produced by MNE from existing template surfaces; no surface
reconstruction, registration, segmentation or new BEM/FEM solver. No all-pairs
source distances are precomputed. mindist=5 mm is MNE's explicit boundary guard;
record actual retained hemisphere/vertex identities, not assumed source counts.

Primary current orientation is signed cortical normal, using vertex normals
(use_cps=False). Preserve the free three-component surface-basis forward for
MNE depth weighting and fixed/free validation. Record basis vectors and source
coordinate frames. Free inverse vectors are linear components, not unsigned
magnitudes; unsigned norms cannot be assigned a fixed linear resolution matrix.
All coordinates are stored in meters. Millimeter conversion must be explicit.

## Noise, reference and inverse

Use all 64 validated EEG channels in fixed canonical order. Apply existing
continuous 1–40 Hz zero-phase Butterworth preprocessing, average reference and
existing QC thresholds over the selected 64 channels. Preserve every accepted
and rejected annotation-contained [1,3) window and original run boundaries.
No interpolation, resampling, ICA or automated artifact diagnosis. Reject bad or
incompatible channels/frames. The average-reference projector must agree for
data, lead field, covariance and inverse; it removes one sensor dimension.
Handle additional explicit projectors by their retained subspace, never by
silently inverting a singular covariance or treating it as full rank.

For each run, use accepted same-run T0 [1,3) rest windows for MNE covariance with
fixed 0.1 shrinkage and rank-aware whitening. Rest includes background neural
activity and possible artifacts; it is a modeling covariance, not empty-room or
instrumental noise. Synthetic evaluation noise and covariance-training samples
use independent random streams. Source priors/noise assumptions are recorded.

MNE supplies minimum-norm operators. Primary depth exponent is 0.8 and lambda2
is 1/9, fixed before real outcomes and not asserted optimal for EEG. Keep nave=1
for single-trial inference. MNE estimates are physical current dipole moments
(A·m); dSPM is optional noise-standardized, dimensionless activity, not physical
current. Small independent SVD Tikhonov examples validate algebra only; they do
not replace MNE's full cortical inverse or equate its prior normalization to an
arbitrary scalar ridge penalty.

## Synthetic and resolution design

Small analytical tests include identity/diagonal, over/underdetermined, rank-
deficient and ill-conditioned systems, correlated/misestimated noise, incorrect
forward operators, orientation handling and regularization limits. Report
identifiability limits instead of demanding exact underdetermined recovery.

Cortical simulation uses the actual template lead field, known signed normal
currents, 10 Hz oscillations, 1e-8 A·m amplitude, separated/correlated sources,
variable scalp clearance, amplitude modulation and bursts. Independent Gaussian
covariance-training noise is distinct from evaluation noise. Fixed primary
lambda2/depth are never chosen using recovery truth. Report all SNRs −10/0/10/20
dB, ten seeds per scenario/SNR, and all predefined regularization/depth sensitivity
settings. Any truth-selected best setting is explicitly oracle-only and cannot
become primary. A 5% synthetic operator perturbation is an abstract mismatch
stress test, not a physically recomputed conductivity model. A separate supported
MNE spherical conductor comparison may vary actual shell conductivity, with a
fresh forward calculation for each model if feasible.

For fixed linear current inverse W and matching lead field L, resolution is W L.
Compute selected PSF columns and cross-talk rows (12 source probes), matrix-free
products and the diagonal, not a dense cortical N×N matrix. Report peak error,
energy-weighted spatial dispersion, leakage and sensitivity to regularization.
Head-coordinate Euclidean distance is not cortical geodesic distance. Optional
white-surface geodesics use mesh edges within a hemisphere; disconnected paths
remain undefined, not converted to fictitious cross-hemisphere surface distances.
Scalp clearance is an approximate geometric depth measure, not cortical thickness.

## Real-data demonstration and interpretation

Subject 1, runs 4/8/12, only. Fit each run's rest covariance separately and apply
MNE inverse epoch-by-epoch with generators. Compute vertex mu/beta power with
NeuroDSP from individual signed source time courses. Average powers over trials
and then equally over runs. Template precentral ROI summaries average vertex
powers, not waveforms with potentially opposing normals. Save numerical maps,
source indices, units, trial counts, QC and background covariance assumptions.

Reconstruct averaged waveforms only as a comparison, with the same nave=1 linear
operator to isolate phase cancellation from a changed regularization/noise scale.
An evoked average is not the sole analysis of induced motor-imagery oscillations.
Source-map log contrasts compare condition mean trial powers within runs, then
average runs equally. MNE and dSPM power units remain separate. No population
p-values, vertexwise significance maps or anatomical truth claims from one
participant. Report residuals, leakage, broad point spread, template mismatch,
rank, nonuniqueness, regularization bias and noise amplification.

## Engineering and provenance

Use bounded workers (one for BEM/forward and BLAS), sequential recording/epoch
processing, atomic checksummed caches and no large raw/templates in Git. Numerical
computation must run without a 3D backend. Headless Matplotlib surface/coordinate
projections are acceptable and explicitly labeled; save arrays and source IDs
under every figure. Cache identities track template/source/BEM/transform/montage,
channels, projector/orientation, code and dependencies. Record CPU/wall time,
peak RSS, seeds, versions and Git revision. Scientific limits are retained even
when a numerical workflow succeeds. No MRI anatomical pipeline or Milestone 7.
