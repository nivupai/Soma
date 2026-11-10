# Longitudinal subject/session audit

Session auditing extends the existing dataset-scoped HMAC identities. It rejects
identical recording declarations and unrelated subject/task/modality scopes, retains
explicit absent sessions and compares acquisition, temporal and spatial declarations.
It labels repeated runs, repeated sessions, repeated acquisitions and different
participant scopes separately. Multiple runs cannot become separate participants or
invented visits. Existing M20 planning also rejects identical primary content assigned
to different recording identities and preserves the entire frozen cohort.

Chronology requires actual acquisition timestamp sources whose hashes and values
match each identity. Session names, alphabetical order and run numbers provide no
visit ordering or interval evidence. Missing sources are INDETERMINATE. Verified
source correspondence still does not establish biometric identity or source authority.

A session identity-alignment PASS covers its stated metadata checks only. It does
not establish common anatomical alignment, identical task implementation, sufficient
preprocessing, acceptable QC, consent or longitudinal reliability. A shared scanner
frame name is not a common anatomical reference. The execution-readiness layer also
requires reviewed evidence, frozen protocol scope, preprocessing/QC and explicit
common-space/task correspondence. That final correspondence is conservatively
INDETERMINATE; independent longitudinal/anatomical attestation is not automated.

Real pilot: EEGBCI's two subjects each have runs4 and8 of unilateral imagery, with
consistent documented event meanings and fixed preprocessing/QC. Four recordings
remain two participants, zero documented visits. ds000114 has one scoped participant
and two explicit sessions; acquisition chronology and audited common-space derivatives
are unavailable. Neither dataset demonstrates longitudinal reliability here.
