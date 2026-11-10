# Human data identity — design contract

Milestone 20 semantics frozen before implementation. Dataset/version, scoped HMAC
participant, explicit session or null, task, run/acquisition, modality, partition,
geometry/time evidence and availability are independent identity fields. Null is
absence, not an invented visit. No cross-dataset or chronological inference is made.
All scheduled records are retained, with explicit eligibility/deviation decisions.

Permission evidence is content-bound, purpose/action-scoped and rechecked at execution,
including expiry/revocation/conflicts. File possession never grants use. Public notices
support only recognized limited actions; missing agreements block execution/export.
This software check is not legal authorization or consent verification. Local evidence,
keys, mappings, participant results and agreements stay outside Git.

New human protocols use the existing M19 declaration/seal schema and registered M18
DAG execution. Human population semantics are a separate explicit adapter; the M19
synthetic-only replay API is unchanged. Actual input hashes, identity, permission
context and preprocessing definitions isolate caches. No inferential human fMRI
execution is authorized. Registration is opt-in, read-only and never automatic
preregistration or promotion to confirmation. No new scientific estimator is added.
