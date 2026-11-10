# External protocol registration evidence

Registration inspection is optional and provider-neutral (`RegistrationProvider`).
The implemented OSF provider performs a bounded read-only HTTPS GET against the
fixed public registration API origin only when explicitly opted in. It never posts,
registers, uploads, authenticates or follows arbitrary redirects. Unsupported/private
access remains UNVERIFIED; credentials are neither requested nor stored.

Receipts use `soma.registration.evidence/1.0.0`: provider/registration ID, source URL,
source registration timestamp, registered protocol ID, full protocol fingerprint,
retrieval state, actual verification-attempt time, source-metadata hash and unresolved
mismatches. No ID or registration evidence was supplied for these Soma human pilots:
external preregistration remains unverified. Nothing has been registered automatically.

Public metadata correspondence uses explicit `soma_protocol_id=...` and
`soma_protocol_fingerprint=...` markers, with exact identity, active/public status
and plausible source timestamp checks. A match is **PARTIAL_PUBLIC_METADATA_MATCH**.
OSF documents that [registration metadata, including descriptions, are editable](https://help.osf.io/article/571-add-metadata-to-your-osf-registration).
Therefore a description hash does not prove the content existed at `date_registered`.
`content_timestamp_attested` and `registered_content_immutability_verified` remain
false. Immutable registered attachment/version correspondence is not implemented.
This limitation is explicit; metadata matching never becomes full preregistration.

Local/imported receipts remain UNVERIFIED unless source retrieval occurs. Injected
providers in tests do not establish production attestation. Test transports and
fictional CI fixtures are not external evidence. Registration metadata verification
never grants consent, data-use permission, statistical confirmation or anatomical
validity. Receipts are linked externally to the unchanged M19 seal fingerprint;
there is no self-referential seal mutation, backdating or timing upgrade.
