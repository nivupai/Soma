# External EEG dataset and permission audit

The initial candidate is BNCI 2014-001, originally BCI Competition IV 2a.
The original BNCI MAT distribution is unversioned; pin local bytes by hashes.
NEMAR nm000139 v1.0.3 is a separate distribution/version, not a substitute name
for the original MAT files. No signal data were acquired or access checkbox accepted.

| Metadata | Audited candidate |
|---|---|
| Participants / actual sessions | 9 / 2 per participant on separate days |
| Task | Left hand, right hand, feet, tongue imagery |
| Binary endpoint | Classes1/2 → left0/right1; exclude3/4 |
| Acquisition | 22 EEG +3 EOG;250Hz; left mastoid reference; right mastoid ground |
| Hardware filtering | 0.5–100Hz and50Hz notch |
| Timing | Trial start0; cue2s; imagery through6s |
| Expected all-class / binary trials | 5,184 /2,592 before QC; metadata expectations only |
| Local inventory | 0/18 original MAT files in permitted raw/external roots |
| Observed external human coverage | 0 subjects,0 sessions,0 trials |

Primary sources: [original experiment description](https://www.bbci.de/competition/iv/desc_2a.pdf),
[BNCI distributor](https://bnci-horizon-2020.eu/database/data-sets),
[NEMAR versioned catalog](https://nemar.org/dataset/nm000139), and
[MOABB loader source](https://github.com/NeuroTechX/moabb/blob/develop/moabb/datasets/bnci/bnci_2014.py).
Cached public metadata and byte hashes remain in ignored reports; the public freeze
receipt records source URLs/hash availability. No participant/demographics table
was downloaded. Metadata retrieval included public third-party benchmark context;
those summaries were not used to choose a dataset, parameters or favorable outcome.
No Soma target labels or external predictions were inspected before sealing.

## Rights and unresolved execution conditions

Both the original BNCI page and NEMAR catalog identify CC BY-ND4.0. This is not a
mirror-only restriction. The [formal CC license](https://creativecommons.org/licenses/by-nd/4.0/legalcode.en)
permits producing/reproducing adapted material privately while restricting its
sharing. Do not interpret an ND summary as a blanket prohibition on computation,
or assume it automatically authorizes every derived artifact. Sharing aggregate
facts may be distinct from sharing adapted recordings; that determination is not
automatically established here. The software gate supports scoped local analysis
from the recognized BNCI notice and separately blocks aggregate export without a
content-bound local review. Accessibility is not verified individual consent.

The original competition additionally requests attribution/citation and reporting
publications; no terms were accepted and no messages were sent. Raw signals,
processed recordings, fitted weights and participant predictions remain private.
No human execution proceeds without both local inputs and the appropriate evidence.

Cho2017/GigaDB DOI10.5524/100295 is an alternative candidate: its primary
[DataCite metadata](https://api.datacite.org/dois/10.5524/100295) identifies CC0-1.0,
whereas MOABB's catalog lists CC BY4.0. Preserve that discrepancy and verify the
exact distribution. It has different session/timing conventions and is not silently
substituted. No alternative data were acquired or selected for execution.

## Prior exposure

A metadata/file-name inventory of the explicitly permitted local roots found no
BNCI/NEMAR EEG files. Search of all reachable tracked Soma source, tests, protocols,
experiments and documentation found no prior BNCI/nm000139 use. This is evidence of
no matching tracked development exposure, not proof of global algorithmic,
population or human-researcher independence. The dataset is widely used in the
literature and its historical evaluation labels are publicly available. Different
filenames do not establish independent model validation.
