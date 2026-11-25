# M33 skull protocol v4: the sealed v3.1 method, tested on CERMEP-IDB-MRXFDG (draft)

Status: **DRAFT**. It becomes sealable only after (a) the CERMEP data arrive and (b) the
**MRI-only pre-check** below passes. Sealing records this file's SHA256 and the model SHA256 in
`configs/m33-skull-v4-freeze.json`.

## Why v4

The v3.1 external test on SynthRAD2025 head-and-neck was inconclusive (0 of 156 evaluable),
because 3 mm radiotherapy MRI is outside the method's scope. CERMEP-IDB-MRXFDG (Mérida et al.
2021) has 37 healthy adults with 1.2 mm MPRAGE and low-dose CT, which matches the method's
intended input.

## Method: unchanged from sealed v3.1

Exactly `docs/MILESTONE33_SKULL_PROTOCOL_V31.md`: head crop, then FreeSurfer 8.1.0 watershed,
then fixed normal offsets (inner −3.28, outer −3.63, scalp −0.95 mm), then the learned inner-skull
refinement with model SHA256 `36c6391132d699decc9d8e34c176c612aac48ef49fddff574b9096206de67f65`,
then MRI-only QC ratio in [0.80, 1.80]. The model is not retrained and no parameter is tuned on
CERMEP.

## Data handling

Native-space data only (DICOM, or NIfTI in subject space), never the MNI-normalised release.
The MPRAGE and CT are used as delivered. If they are not already on one grid, the CT is the
reference geometry. Registration MPRAGE→CT is **rigid, mutual information**, fitted once per
subject using MRI and CT intensities only (never any skull estimate). Its residual is checked
on the head-mask boundary, and a subject whose scalp boundary misaligns by more than 2 mm median
is flagged `registration` and leaves the primary analysis. Only aggregates are published, under
the licence's bona-fide-research terms.

## MRI-only pre-check (must pass before sealing; reads no CT)

On 3 subjects, picked by sorted ID (first, middle, last):
1. the crop, SynthSeg and watershed all complete without error;
2. SynthSeg intracranial volume is between 1,000 and 2,000 mL;
3. the MRI-only QC ratio is inside [0.80, 1.80];
4. peak memory stays under 10 GB and runtime under 20 min per subject.

The pre-check passes if checks 1 and 4 hold for all 3 subjects and checks 2–3 hold for at
least 2 of 3. This rule was set by trying the pre-check on two datasets that were already used.
On 3 SynthRAD2023 brain subjects (in scope) it **passed**: two clean, one with QC ratio 1.96.
On 3 SynthRAD2025 head-and-neck subjects (out of scope) it **failed**: QC ratios 3.35, 4.11, and
no brain found. It would have stopped the v3.1 head-and-neck test before sealing.
If the pre-check fails, the cause is reported and the protocol is revised **before** sealing.
These 3 subjects remain in the test set, because no CT has been seen.

## CT truth, flags, metrics, decision rule

Unchanged from v2/v3.1 (`FLAGS_V2`; bone at 300 HU primary, 200/400 sensitivity). The same
VALIDATED / QC_ONLY / NOT_READY rule applies, with the owner-approved limits and at least 15
evaluable subjects. Every subject is scored once.
