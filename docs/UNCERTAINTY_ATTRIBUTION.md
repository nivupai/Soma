# Paired uncertainty attribution

The source model is the participant sample geometry with a known simulated
10-nA m signed normal current at index 281. The baseline forward and current are
held fixed for generation. Independent 10,000-sample training noise estimates
covariance; evaluation uses 40 independent Gaussian sensor snapshots from a
separately named SeedSequence stream. Training scale is fixed at 1 µV; evaluation
noise is rescaled to expected SNR 0/10/20 dB. The assumed training covariance and
regularization are not refitted to those evaluation levels. All colored-noise
arrays, evaluation covariance and scale, truth, forward operators and inverse
cache identities are saved.

The same 40 noise vectors pair every comparison. One-factor changes are MRI-x
translation 3 mm; electrode-coordinate Gaussian SD 3 mm per axis (one assigned
geometry realization); skull conductivity 0.003 S/m; lambda²1; and 3-degree MRI-z
rotation as a distinct forward mismatch. They are assigned model settings, not
sampled biological variation. New conductivity/combined geometry configurations
rebuild or retrieve independently fingerprinted physical BEM/forward solutions.
Every inverse cache binds its actual forward, covariance/projectors, channels,
source IDs/basis, depth, orientation, method, lambda and software/code versions.

A limited 2³ factorial crosses registration translation, skull conductivity and
regularization. Difference-of-differences uses common noise draws and holds other
factors at their low reference levels. Pairwise and three-way interactions are
reported rather than forcing an additive decomposition of nonlinear source-error
or localization metrics. There are 17 settings × 40 draws = 680 source evaluations,
with no numerical failures in the executed design.

The baseline noiseless relative current error is 0.993987. Mean correct-model
error at 10 dB is 0.998367. Paired changes are approximately +0.0000885 for
registration, +0.000661 for electrode jitter, +0.005857 for skull conductivity,
+0.0000228 for rotation and −0.002382 for stronger regularization. These describe
this source, metric and assumptions; the dominant baseline point-spread bias
remains. Lower total error with stronger regularization is compatible with greater
true-vertex amplitude attenuation because it reduces noise elsewhere.

Registration×conductivity interaction is −0.0001772, conductivity×regularization
−0.0055386, and the three-way interaction +0.0001761. The stored paired 95%
Student-t simulation intervals quantify uncertainty of the mean across these
40 independent noise draws. They are approximate simulation intervals, not
anatomical credible intervals or population generalization. A single fixed
geometry realization does not estimate a distribution of anatomical errors.
No variance-based biological decomposition is claimed.

Mean peak error decreases from 68.37 to 40.35 to 27.46 mm as expected sensor SNR
increases 0→10→20 dB. These are independent noisy **single snapshots** with paired
streams, different from the historical 640-sample temporal-energy localization
metric; their absolute values should not be treated as a correction to M8.
The report preserves baseline error, total error, paired changes, interaction
arrays, rejected controls and all seeds. A small polynomial factorial oracle
independently checks that additive factors cancel and known interactions recover.
