# Milestone 8 participant source validation

Soma 0.8.0 adds a conditional participant-matched research workflow. It does not
establish anatomically certified individualized EEG localization. All original
421 tests remain unchanged. Machine-readable executed results, software versions,
source hashes and verification are in
[`experiments/milestone8/verification.json`](../experiments/milestone8/verification.json).
Reports and numeric figure companions are local under `reports/milestone8-verified/`;
large downloaded assets and generated reports remain excluded from Git.

## Dataset and deviations

Primary is the official MNE sample audiovisual participant, matching paths
`MEG/sample` and `subjects/sample`, source subject IDs `sample`. The recording
lacks populated `subject_info`; correspondence relies on curated dataset identity
and internally consistent assets, not independently authenticated identity.
The sample archive is obtained only by explicit `anatomy inspect --fetch`.
MNE's public fetcher supplies the full archive, not selected resources. The
2.7-GiB extracted/cache directory and bounded physical caches fit the 8-GiB study
budget. The archive URL/MD5, selected-file SHA256, release version, MRI geometry,
transform matrices, channel/source identities and package versions are recorded.

The official [MNE dataset documentation](https://mne.tools/stable/documentation/datasets.html#sample)
describes educational/tutorial use and warns against hardware/MRI-system performance
evaluation. No standalone SPDX dataset license was found in the archive, so no
BSD or CC license is invented. This study follows the documented educational scope.
Secondary ds000117 metadata discovery was executed, with current BIDS license
CC0, 16 participant IDs and a separately excluded empty-room recording. Optional
exact selected-subject retrieval is implemented with path/identity guards and a
byte budget; no secondary participant data or head model was downloaded/run.
The historical OpenfMRI license must not be substituted for the current snapshot.

The original sealed watershed assumption was corrected by the documented
[amendment](INDIVIDUAL_HEAD_MODEL_AMENDMENT.md), without rewriting the prespecified
protocol/configuration. Default sample surfaces resolve to FLASH. No measured
MRI fiducial file exists. The primary distributed transform and inverse settings
were retained; no recovery-based model selection occurred.

## Geometry and forward

There are 60 EEG channels, 59 retained after excluding EEG053, 61 digitized EEG
points including reference, 3 cardinal fiducials, 78 EXTRA headshape and 4 HPI.
Retained electrode labels and coordinates match their digitized identities exactly
(max discrepancy 0 m). None is replaced by a template montage or headshape point.
Only the retained-channel average reference is used; unrelated MEG SSP is removed.

Primary residuals against **MNI-derived** MRI fiducial proxies are approximately
23.51/10.03/27.36 mm (LPA/nasion/RPA). These are not independent registration
errors; the 20-mm anatomical truth gate is INDETERMINATE. Exact headshape/scalp
RMS is 4.651 mm before and 4.598 mm after comparison ICP. The primary transform
is unchanged. Synthetic noiseless rigid translation error is 2.60e-18 m and
rotation error 7.19e-15 degrees. With 1/3/5-mm fiducial SD, actual translation
error is 0.965/2.915/4.890 mm and rotation error 1.017/3.119/5.315 degrees.
Weighted SVD agrees with MNE within the saved numerical tolerance.

All three solver meshes pass topology, intersection, nesting and quality tests;
minimum gaps are 3.238/3.476 mm. Overall readiness remains **INDETERMINATE** due
to unsupported independent anatomical evidence; computational readiness is PASS.
The actual EEG forward is **59 × 1,239**, fixed signed cortical normals, rank 58.
A fresh independent MNE construction agrees within the integration-test tolerance.
The reference inverse comparison checks Soma's adapter against direct MNE use,
not independent anatomical accuracy. Native free-orientation forward is retained
for depth weighting. Optional MEG fallback is separately labeled forward-only;
its actual sensor/source dimensions are recorded in the verification receipt.

## Sensitivity and signal example

A 5-mm MRI-x translation changes the lead field 6.22%; a 5-degree rotation 11.35%;
5-mm per-coordinate electrode SD 15.49%. Scalp-low/skull-low/skull-high/brain-high
conductivity alternatives change it 14.50/33.63/37.33/15.06%, respectively.
Unperturbed fiducial refitting alone changes it 40.58%; this method change is
separated from added fiducial measurement noise. Headshape refitting alone
changes it 3.23%. These are single-subject methodological sensitivities.

For simulated cortical truth, even the correct-model inverse has **28.315-mm peak
error and −98.967% current-amplitude bias** at the generating vertex. A 5-mm
electrode-noise condition has 37.524-mm peak error; some mismatches reduce peak
error to about 21 mm while retaining severe bias/leakage. No mismatched model is
promoted on this basis. Per-case metrics, rejected cases and covariance seeds
are saved; no anatomical accuracy or population inference is established.

The real EEG example uses actual auditory-left/right and visual-left/right codes
1/2/3/4, first 12 accepted epochs each (48 total), −0.2…0.5 s, baseline −0.2…0 s,
150-µV rejection, fixed 0.1-shrunk prestimulus background covariance and response
window 50…200 ms. Trialwise and evoked inverse linearity agrees near 1e-15.
Evoked/trialwise 8–13-Hz power ratios are 0.118/0.098/0.248/0.288. These short
0.7-s epochs have about 1.42-Hz Welch resolution. Averaging removes both phase
variation and noise; these ratios do not isolate induced activity. This is an
audiovisual example, not motor imagery or real-source localization truth.

## Reproduction and acceptance

Run `sh experiments/milestone8/run.sh reports/my-m8-run` after explicit sample
fetch. Every output directory must be new. The script runs synthetic controls,
coregistration, BEM validation, individual forward/inverse, perturbations and the
optional separately labeled MEG forward. Seed 42, one worker. Content-fingerprinted
BEM/source/forward caches retain checksums and stage times; conductivity rebuilds
physical solutions. Manifests include recursive output hashes and the exact Python
source-tree hash, including runs made before the local release commit.

All ten requested figure categories have numeric NPZ companions and were visually
inspected: MRI alignment, fiducials, scalp distance, three boundaries, quality/gaps,
spectrum, perturbations, conductivities, localization and truth/recovery. No dense
full cortical resolution matrix is allocated. Representative workflow times and
process high-water RSS are in the verification receipt; RSS includes libraries
and is not incremental memory. Real inverse and sweep remain under 1 GiB here.

Unsupported: independent MRI landmark truth, individual conductivity estimation,
anatomical/clinical certification, independent alternate anatomy, full native
high-resolution geometric certification, new FreeSurfer generation, ds000117
participant reconstruction and population generalization. Milestone 6 APIs and
Milestone 7's failed SPM foreground/BEM result are preserved. No Milestone 9 work
or remote push is included.
