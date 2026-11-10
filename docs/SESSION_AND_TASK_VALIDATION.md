# Session and task validation

Identities use dataset/version, a dataset-scoped HMAC subject, explicit nullable
session/run/acquisition, task and modality. Identical raw identifiers in independent
datasets never imply the same person. Raw-to-pseudonym mapping is checked in memory
using the private key before dispatch; the key never enters workflow inputs, graphs,
caches or records. Dataset file hashes and roots are checked before and after execution.

EEGBCI uses the existing run-specific T0/T1/T2 mapping and lazy EDF loader: 64 EEG
channels at 160 Hz, documented run identity and nonempty expected annotations.
Runs 4/8/12 are unilateral imagery; 3/7/11 are movement, 6/10/14 bilateral imagery,
and 1/2 baseline. Only the established unilateral imagery pipeline is executable
through this pilot. Trials and repeated runs do not become independent participants.

IBSR pairing requires explicit stripped T1/non-filled tissue reference roles and
subject identity; conflicting duplicate resources are rejected. Identical compressed
and uncompressed copies may be resolved only after comparing decompressed content.
The existing M11 loader validates native sform/spacing, singleton frames, units and
label codes; the existing scorer checks matching subject, space and physical grid.
MRBrainS adapters accept only the documented training partition; the existing local
Readme/manifest identity checks are reused. Hidden test payloads are never opened.

Legacy ds000114 is indexed with PyBIDS without falsely certifying current BIDS.
Directory/file entities, task metadata, TR, event timing, structural correspondence
and explicit session/run absence are checked. Missing audited preprocessing,
confounds/QC and transform provenance block GLM execution, even if filenames resemble
derivatives. Session labels alone never establish order. `chronology` verifies
explicit timestamps against hashed acquisition metadata; it does not establish
human reliability. The current real pilots have no verified acquisition chronology.
