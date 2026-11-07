# Milestone 9 model reliability protocol

Baseline: Soma 0.8.0, e7cf639, 461 tests. This protocol follows inspection of the
actual M8 code, report arrays, metrics, transforms and installed MNE signatures.
It precedes new reliability algorithms and parameter sweeps. Old results remain
immutable. The purpose is explanation and bounded validation, not improved scores.

## Initial audit and interpretation

The historical correct-model case uses 59 average-referenced EEG sensors, 1,239
fixed signed normal sources, rank 58, MNE depth 0.8, lambda²=1/9, nave=1, no CPS.
Ground truth is a 10-nA m, 10-Hz current at the source nearest MRI
[-0.04,-0.02,0.05] m (index 281, lh vertex 71803). Noise training uses 10,000
independent colored samples (1-µV scale); evaluation uses independent colored
noise scaled to expected SNR 10 dB. The reported amplitude bias is
norm(jhat[truth,:])/norm(j[truth,:])-1 = -0.989671361410299. These quantities have
compatible A m units. It is unsigned RMS attenuation at the generating vertex,
not total recovered current, a signed waveform coefficient or a dSPM statistic.
Peak error 28.314991 mm is the location of maximum temporal energy versus the
known simulated vertex; no real neural truth exists.

Initial categories: no confirmed numerical error; expected distributed-estimator
attenuation is a hypothesis requiring K=W L validation; effects of depth,
regularization, noise and orientation remain parameter-sensitive; exact causes
of the residual bias are not yet quantified. Fiducial proxy discrepancies are
confirmed but independent anatomical registration accuracy is unsupported.
The MRI targets are MNI-derived estimates; the distributed transform need not
fit them. Their 23.51/10.03/27.36-mm discrepancies are not measured truth error.
FLASH conductor provenance and the documented M8 amendment are retained.
Initial machine audit and checksums will be saved independently of old reports.

## Prespecified computations

1. Reproduce unchanged M8 coregistration and complete uncertainty workflows from
cached assets before changing numerical behavior. Verify old report hashes.
Audit HEAD→MRI direction, metres, cardinal identity, headshape/electrode/HPI
separation, measured sensor correspondence, source/boundary frame/subject IDs.
Compare distributed transform, Soma equal-weight SVD, MNE equal-weight
fit_matched_points and supported Coregistration(fiducials='estimated') fitting.
MNE fiducial fitting uses weights 1/1/1; ICP uses only headshape (fiducial, EEG,
HPI weights zero), no scaling, 30 iterations. Record that MNE uses its loaded
scalp, while Soma uses ico3 nearest vertices. Do not replace the reference.

2. Synthetic asymmetric head: radially distorted ellipsoid mesh, fixed known
rotation [8,-5,12] degrees and translation [4,-3,2] mm. Four fitting landmarks and
eight independently positioned held-out landmarks. 100 repetitions per scenario:
independent 2-mm SD Gaussian landmark noise; correlated 2-mm SD noise (correlation
0.6 between landmarks); anisotropic SD [1,2,4] mm; incorrect correspondence;
20-mm outlier; 2-mm headshape noise; partial positive-x coverage; and 60-degree
initial-orientation error. Robust outlier fit is separate, not a silent repair.
Known-noise delta-method 95% 3D target ellipsoids use finite input derivatives;
coverage uses one prespecified held-out landmark and a Wilson binomial interval
across independent repetitions. Report training residual versus held-out TRE,
rotation/translation errors, ICP failure/initialization sensitivity and transform
parameter covariance. Intervals concern the assigned synthetic Gaussian model,
not anatomical uncertainty for the participant. No coverage claim for mislabeled
or outlier/ICP scenarios without a defensible noise model.

3. Full participant inverse: methods MNE, dSPM, sLORETA; lambda²
[0.0001,0.001,0.01,1/9,1]; fixed (loose=0), loose=0.2 vector, free=1 vector;
depth [0,0.8]. Primary historical comparison is fixed/depth0.8/lambda²1/9.
Selected sources: the historical vertex plus deepest/shallowest source under
nearest-inner-skull distance (geometry, not estimator outcome). No oracle
regularization selection. MNE alone has A m units; normalized methods report
pattern/localization/residual diagnostics without physical amplitude bias.
Vector outputs stay linear Cartesian vectors; pooled norms are labeled nonlinear.
Compare noise-free recovered coefficients with selected resolution columns;
save signed true-source gain, all diagonal gains, selected PSFs/CTFs, singular
attenuation, noise amplification and depth. Do not allocate a dense Nsources² K.
Small diagonal-matrix Tikhonov tests provide independent exact numerical oracles.

4. Anatomical evidence: distinguish computational verification, externally
supported reference, heuristic assessment, not assessed and failed. Audit MRI
geometry/provenance, segmentation origin, FLASH generation, coordinate chain,
solver topology/nesting/intersections/winding, sensor geometry and anatomical
plausibility. Use available aseg/brainmask as same-pipeline derivatives, never
independent truth. No skull/scalp truth mask or Dice claim is invented. Quantify
surface-to-mask distances and fraction of derivative-mask voxel centers inside
inner skull, with bounded deterministic sampling; report distributions in mm and
explicitly identify heuristics. Synthetic analytic spheres verify displacement,
normal orientation and connectedness. Overall anatomy stays INDETERMINATE when
independent evidence is unavailable; the SPM foreground rejection is unchanged.

5. Paired one-factor and limited factorial attribution: synthetic current on the
participant baseline forward, 40 independently seeded Gaussian sensor-noise
realizations at SNR [0,10,20] dB. Separate 3-mm MRI-x registration translation,
3-mm per-coordinate electrode jitter, skull conductivity 0.003 S/m, lambda²1,
and a 3-degree rotation as a distinct forward mismatch. Noise covariance is
independent of evaluation draws. Limited 2³ factorial uses registration,
skull conductivity and regularization; common random numbers pair every cell.
Report mean errors, paired changes, 95% Student-t simulation intervals, differences
of differences and failures. These are interactions of metrics under assigned
settings, not an exact additive or variance-based biological decomposition.

## Reproducibility and acceptance

Seed 42 with named independent SeedSequence streams. Frozen YAML/receipt bind
all parameters. No download is implicit. MNE remains the established full inverse
backend; old adapters and commands retain contracts. New inverse cache binds
forward, covariance/projector, source/sensor IDs, orientation, depth, method,
lambda, code and versions. Corrupt/incomplete caches fail closed.
Use one worker, <=2 GiB process memory target, bounded source selections and mask
samples, no full-resolution K. Record stage wall/CPU time, high-water RSS,
versions, Git state, transforms, sources, inputs and recursive output hashes.
Ten requested figure categories have numeric companions and units/truth/sample/
estimator labels. All 461 prior tests must pass byte-unchanged; add independent
numerical, offline and opt-in anatomical tests. Run Ruff/format/strict mypy/pip
checks and actual five new commands plus previous workflow regressions. Record
unsupported claims and unfavorable outcomes. No clinical certification, no push,
no automatic Milestone 10. Any correction needs provenance and a regression test.
