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
