# Immutable registration evidence — v0.21.0

The existing read-only provider inspector is extended with an `AttachmentProvider`
interface and a concrete fixed-origin OSF native-storage metadata adapter. No study
is registered automatically. Provider access requires explicit opt-in. No credentials,
redirects, arbitrary provider URLs, attachment download or POST are supported.

`verify_attachment` checks actual supplied protocol/seal attachment bytes, protocol
identity/fingerprint, exact registration/file/numeric version identities, registered
file membership, native OSF Storage, current revision, provider SHA-256 and size,
public/active/completed-archiving state, and provider creation/registration timestamps.
The exact local byte hash must match the provider hash; a description containing a
fingerprint is insufficient. Retrieved metadata fingerprints, endpoint identities,
selected provider metadata, method, verification time and limitations are retained.

| Evidence state | Meaning |
| --- | --- |
| VERIFIED_IMMUTABLE | Concrete OSF retrieval satisfies all supported immutable-file checks |
| PARTIALLY_VERIFIED | Some matching evidence exists but source/version evidence is incomplete, or provider is an injected fixture |
| UNVERIFIED | Offline, unavailable, malformed or unsupported retrieval evidence |
| MISMATCH | Protocol, content, identity, membership, size or known source assertions contradict the request |
| NOT_AVAILABLE | Required local attachment is absent |

Only the **current numeric revision of a native OSF registered file** is supported.
Historical revision hashes, third-party storage, authenticated/private registrations,
unsupported identifiers and failed/ambiguous archives cannot be verified. Injected
providers never produce production attestation. A test that intercepts the concrete
adapter transport exercises its branch using synthetic records; it is not a real
verified registration.

OSF documents registered files as frozen, while descriptions and other metadata may
be edited. This implementation relies on those provider semantics and HTTPS source
retrieval; it is not a cryptographic timestamp authority, proof of authorship, proof
of a prospective study, legal authorization or statistical confirmation. Offline
receipts are historical evidence and must be revalidated for current use.

No accessible Soma registration or attachment identifier was supplied for this
milestone. **Actual externally verified registrations: zero.**

Primary sources reviewed:
- [OSF registered-file restrictions](https://help.osf.io/article/387-files)
- [Editable registration metadata](https://help.osf.io/article/571-add-metadata-to-your-osf-registration)
- [Official registered-file endpoint specification](https://github.com/CenterForOpenScience/developer.osf.io/blob/master/swagger-spec/registrations/file_detail.yaml)
- [Official version endpoint specification](https://github.com/CenterForOpenScience/developer.osf.io/blob/master/swagger-spec/files/version_detail.yaml)
