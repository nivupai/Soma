# EEG–fMRI spatial interface and capability boundary

Mode cross-dataset compares explicitly identified regional tables descriptively.
Each modality supplies dataset/release/subject, visit/task, quantity, ROI ontology,
regional values and spatial provenance. Identical ROI names alone are insufficient
without declared ontology and evidence. Scales remain different; correlation is
one descriptive statistic, never proof of coupling, participant correspondence or
population generalization. The numerical demonstration uses simulated values only.

Mode participant-matched additionally requires same subject within one dataset
release and explicit shared visit and task mappings. Different releases/subjects,
missing spatial evidence, incompatible regions and absent mappings fail. EEG and
fMRI quantities are distinct; simultaneity is never inferred. Required evidence
is caller supplied and must be independently audited; a nonempty receipt does
not establish that an external registration was anatomically correct.

Metadata inspection of the public OpenNeuro ds000117 repository confirms that
MRI and MEG files exist; EEG may be embedded in MEG FIF rather than standalone
EEG files. Recordings/channels were not downloaded or inspected. The provider
README documents a16-person subset, altered numbering relative to older releases,
separate MRI/MEG visits, familiar/unfamiliar/scrambled face conditions and already
removed dummy volumes. Never match IDs across releases without that release's
mapping, or shift event timing again by assuming dummy volumes remain. An adapter
inventories local modality files and reports requirements, not matched readiness.

The inspected ds000114v1.0.2 repository documents test/retest sessions and
finger/foot/lips tasks, but the selected metadata inventory provides no preprocessed
BOLD/confound tables. No raw fMRI was promoted to validated derivatives. Real
human test/retest and EEG/fMRI comparisons are therefore unavailable. No full
OpenNeuro dataset was downloaded. The SPM educational example is a separate
single-subject auditory task; it cannot be participant-matched to Soma motor EEG.

Even with future matched data, registration error, spatial smoothing, EEG inverse
leakage and physiological variation need separate measurement. BOLD's hemodynamic
response and EEG oscillatory power/current differ in timing, scale and mechanism.
No joint estimator, deep fusion, simultaneity claim or anatomical certification is
implemented. Synthetic perturbation plots illustrate identifiable toy causes only.

Sources: [provider ds000117 README](https://github.com/OpenNeuroDatasets/ds000117/blob/master/README),
[ds000114 description](https://github.com/OpenNeuroDatasets/ds000114/blob/master/dataset_description.json).
