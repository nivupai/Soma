# Milestone 25 external authorization and selection

No dataset was approved or selected for human execution. No recordings were acquired,
click-through terms accepted, credentials supplied or human target predictions made.
The current audit is metadata only. The original upstream distribution must not be
silently replaced by a differently licensed/versioned mirror.

| Candidate | Authoritative evidence | Decision |
|---|---|---|
| BNCI2014-001 | Unversioned upstream18MAT; [BNCI distributor](https://bnci-horizon-2020.eu/database/data-sets) identifies CC BY-ND4.0; [NEMAR nm000139](https://nemar.org/dataset/nm000139) v1.0.3 is a distinct1.38GB distribution | Primary well-documented feasibility audit; nine participants/two sessions,22EEG/250Hz. Reference mismatch prevents scientific equivalence; local-analysis notice support does not clear aggregate export. |
| Cho2017 | [GigaDB DOI10.5524/100295 primary DataCite rights](https://api.datacite.org/dois/10.5524/100295) identify CC0-1.0; MOABB catalog CC BY4.0 discrepancy retained | Preferred next acquisition-rights review because of primary CC0 evidence, subject to exact distribution/manifest review.52 participants,64EEG/512Hz, one session. Original units/reference/cue mapping remain unverified for execution. |
| BNCI2014-004 | Same original BNCI distributor; CC BY-ND4.0,18MAT containers corresponding to nine people/five actual sessions | Three bipolar C3/Cz/C4 channels; six required ROI channels absent. Frozen transfer incompatible; no interpolation. |

Preference is based on rights, task/montage/session metadata and reviewability,
not observed Soma target accuracy. No matching earlier tracked Soma development
exposure was found in M23's audit; worldwide algorithm/participant independence
is not established by filenames or a different dataset namespace. Public metadata
can include historical third-party benchmark context; this is not a blinded review.

CC0, CC BY and CC BY-ND notices do not establish individual consent or every intended
use. ND private adapted analysis and sharing are separate questions. Aggregate
publication needs its own reviewed permission scope. No new external M20/M21
review bundle or explicit acquisition approval was supplied.

## Actionable acquisition procedure

1. Select the exact original distribution and obtain its verified file URLs,
   byte lengths and SHA256 manifest. Sizes/checksums currently unknown stay unknown.
2. Review source terms, intended local analysis and aggregate export. Resolve
   Cho's catalog discrepancy against the actual distribution. Do not infer consent.
3. Seal a fresh input-bound harmonization revision. Filling template hashes changes
   its fingerprint; the present incomplete proposal cannot authorize a download.
4. Supply current M20 permission and M21 reviewed evidence bound to the dataset,
   distribution version, protocol and exact manifest. The separate human approval
   document must match `soma.acquisition.approval/1`, assert `approved=true`, bind
   `manifest_fingerprint`, and declare `terms_acceptance_delegated=false`.
5. Only then explicitly invoke `soma benchmark external acquire REQUEST`. This
   procedure requires preverified SHA256/size values; it does not discover expected
   checksums by downloading unapproved recordings. A missing trusted manifest is
   an acquisition blocker to resolve with the provider or reviewed local files.

The acquisition agreement is an M21 `agreement` entry with reviewed `acquire`,
`analyze` and `export_aggregate` scope. Permission/readiness, hash, validity/revocation,
purpose and distribution checks run before network access and before each file.
Approval is a local review assertion, not cryptographic authentication or a legal
consent determination. No approval-construction command impersonates the user.

Only bounded HTTPS direct files on reviewed source hosts are supported. Redirects,
URL credentials/query tokens, unknown lengths, checksum mismatches, symlinks,
changed existing files and overwritten inputs are refused. Atomic exclusive writes
retain verified partial progress without accepting corrupt partial files. Raw
storage and receipts must be separate ignored roots. Snapshot verification proves
bytes/identity, not scientific eligibility; parser/event/QC validation remains separate.
