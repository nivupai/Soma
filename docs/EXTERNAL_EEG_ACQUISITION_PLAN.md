# External EEG acquisition plan — metadata audit

Status: **EXTERNAL_DATA_ACQUISITION_BLOCKED**. No external signals were acquired,
website terms accepted, credentials supplied or human target inference performed.
The reproducible machine-readable plan is `experiments/milestone24/acquisition-plan.json`.
Source URLs, distributions, expected file counts, unknown sizes, checksum procedures,
relative permitted root and required authorization are explicit. Unknown upstream
sizes/checksums are not substituted from a different mirror.

| Candidate | Distribution / rights evidence | Compatibility and decision |
|---|---|---|
| BNCI2014-001 | Upstream unversioned18MAT; NEMAR nm000139v1.0.3 separate. Both identify CC BY-ND4.0 | Nine subjects/two sessions;22EEG+3EOG/250Hz. Nominal nine ROI names present; reference/hardware/timing differ. Local-analysis notice support does not clear aggregate export or supply M21 review. |
| Cho2017 | GigaDB DOI10.5524/100295; primary DataCite CC0-1.0; MOABB catalog CC BY4.0 discrepancy retained |52 participants/one session;64EEG/512Hz;52 expected MAT. Exact file manifest, channel/reference/unit/cue semantics require review. No acquisition authorization. |
| BNCI2014-004 | Unversioned18upstream MAT containers; CC BY-ND4.0 | Nine subjects/five actual sessions;3bipolar EEG/250Hz. Left/right imagery compatible at the task level, but six required ROI channels absent. Exact transfer incompatible; no interpolation. |

Sources inspected read-only:

- [BNCI distributor and per-dataset licenses](https://bnci-horizon-2020.eu/database/data-sets).
- [Original IV2a description](https://www.bbci.de/competition/iv/desc_2a.pdf).
- [Original IV2b description](https://bnci-horizon-2020.eu/database/data-sets/004-2014/description.pdf).
- [Cho primary rights metadata](https://api.datacite.org/dois/10.5524/100295).
- [MOABB original Cho loader/metadata](https://github.com/NeuroTechX/moabb/blob/develop/moabb/datasets/gigadb.py).
- [NEMAR distribution](https://nemar.org/dataset/nm000139).

BNCI IV2b has three labeled training sessions and two historical competition test
sessions; upstream MAT containers and original GDF sessions are different file
layouts. Do not infer untouched labels or session order from file count alone.
Cho requires exact-distribution review of its left/right streams, cue origin and
EOG/EMG handling. The catalog/loader includes historical benchmark context; candidate
selection here uses the requested task and rights evidence, not observed Soma target
accuracy. This is not a blinded literature review.

CC0/CC BY/CC BY-ND notices do not verify individual consent or every intended use.
ND private adaptation and sharing are distinct; aggregate publication needs separate
review. Before acquisition, the user must explicitly authorize the exact dataset and
distribution, size/file plan and destination. Before analysis, the existing M20/M21
content, scope, protocol, expiry and review gates apply. No such authorization or
external reviewed bundle was supplied. No downloader or license-acceptance path was added.
