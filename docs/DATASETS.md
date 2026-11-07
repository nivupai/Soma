# Dataset contract

[PhysioNet EEG Motor Movement/Imagery Dataset v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/)
contains 64-channel EDF+ EEG sampled at 160 Hz. Dataset metadata is recorded in
`datasets.registry.REGISTRY`. The distribution license is Open Data Commons
Attribution License v1.0; see the source terms. No dataset files are redistributed
in this repository.

Cite Schalk, G. (2009), EEG Motor Movement/Imagery Dataset (version 1.0.0),
PhysioNet, doi:10.13026/C28G6P. Also cite Schalk et al. (2004), BCI2000: A
General-Purpose Brain-Computer Interface (BCI) System, IEEE TBME 51(6):1034–1043,
and the PhysioNet publication requested by the source page.

| Runs | Task | T1 | T2 |
| --- | --- | --- | --- |
| 1 | Eyes-open baseline | Not applicable | Not applicable |
| 2 | Eyes-closed baseline | Not applicable | Not applicable |
| 3,7,11 | Movement | Left hand | Right hand |
| 4,8,12 | Imagery | Left hand | Right hand |
| 5,9,13 | Movement | Both fists | Both feet |
| 6,10,14 | Imagery | Both fists | Both feet |

T0 is rest for task runs and baseline for runs 1/2. No left/right interpretation
is reused for bilateral task runs. Subject indices are 1–109; run indices 1–14.
Some recordings elsewhere in this dataset have known quality or sampling issues;
Soma rejects inconsistent sampling/channel metadata rather than resampling it.
Validation of subject 1/run 4 is not a quality guarantee for every recording.

`fetch(root, subjects, runs)` calls MNE `eegbci.load_data` for only the explicit
selection, with `update_path=False`. It never requests a dataset-wide download,
forces replacement, or modifies MNE's configured data path. The canonical cache
is `root/MNE-eegbci-data/files/eegmmidb/1.0.0/S###/S###R##.edf`.
`load_recording` never downloads: it uses `read_raw_edf(preload=False)` and
`eegbci.standardize`, validates 64 EEG channels and 160 Hz, then extracts events
and annotations. MNE converts physical EDF signal units to SI volts. There is
no filtering, reference change, resampling, artifact rejection or montage
assignment. Original and normalized channel labels are both retained in metadata.

Events are integer samples from `mne.events_from_annotations`; event codes are
explicitly T0→1, T1→2, T2→3. They are analysis codes, not original PhysioNet
numeric target codes. Annotation onset/duration in seconds is also retained.
Task recordings must contain T0/T1/T2; unknown or missing labels raise errors.
This validates labels, not the behavioral correctness of every trial.

The real experiment selects C3, Cz, C4 where present. It reports whole-record
spectra and band integrals; rest and imagery are mixed. It makes no condition
comparisons and no statistical claims. Only label metadata is inspected; no
measured sensor positions or forward geometry are inferred.

## Milestone 2 event and geometry layer

The new motor-imagery pipeline preserves the loader's original annotation values,
onsets and durations, and validates a typed event table. Recording-relative
sample indices are derived through MNE with explicit handling of `first_samp`.
Only unilateral imagery runs 4, 8, 12 are accepted by this particular workflow.
Other task types remain valid for the general dataset adapter and event parser.

`assign_geometry` creates a copy with exact matches to the installed MNE 1005
template (current `colin27_1005`, legacy `standard_1005`). Its finite head-frame
coordinates in meters are explicitly marked template, not subject measurements.
The Milestone 1 loader itself still assigns no montage and performs no filtering.

Annotation durations determine whether a proposed analysis or reference interval
is supported. An onset alone is not a trial-duration model. Invalid event tables
fail before analysis; unsupported extraction windows are individually logged.
Runs 8/12 are supported but were not downloaded during this milestone; multi-run
identity preservation was tested offline with deterministic synthetic fixtures.

## Milestone 3 cohort validation

The requested real cohort is subjects 1–5, runs 4/8/12, explicitly fetched as
15 EDFs. No other subjects or runs were downloaded. Every record is processed
separately, checked by the existing adapter, and compared for full EEG channel-set
and sampling-rate compatibility. Failure summaries retain missing, incomplete,
unsupported-annotation, geometry and sampling errors. No outside exclusion list
is applied; any future exclusion must appear with its reason and identity.
Optional expansion to 1–10 requires explicit configuration and fetch.

## Matched anatomy in v0.8.0

`datasets.matched.SampleAssets` explicitly fetches/inspects the curated MNE sample
EEG/MEG/MRI participant. It records MRI geometry, file hashes, digitization kinds,
measured electrode label correspondence and the distributed head→MRI transform.
The full public sample archive is required by MNE's fetcher; no fetch happens on
import or source construction. Default conductor surfaces resolve to FLASH.
`datasets.openneuro` discovers ds000117 metadata and optionally downloads only
explicit selected-subject files with a byte budget. Empty-room recordings are
not participants. Secondary metadata discovery does not establish a usable head
model. See INDIVIDUAL_SOURCE_VALIDATION.md for identity and license limitations.

## MRI references in v0.10.0

The separate typed imaging reference registry lists official McGill BrainWeb and
author Mindboggle-101. BrainWeb's validated target is the original-normal provided
discrete tissue phantom, not a threshold mask. Mindboggle's selected native labels
are manual DKT31 cortex, not a tissue-segmentation standard. Explicit selected
fetches use verified official forms/ranges and preserve raw label IDs, metadata,
license/source attribution and SHA256. The unavoidable NKI cohort transport is
separate from the one-subject retained subset. See MILESTONE10_DATA_PROVENANCE.md.
