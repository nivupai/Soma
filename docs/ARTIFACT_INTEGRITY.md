# Artifact integrity and bounded serialization

Use soma.sdk.results.create_result, validate_result, save_result, inspect_result,
load_result, verify_integrity and verify_provenance. Inputs/outputs are explicit
Path objects and strict JSON dictionaries; numerical arrays are separate mappings.
save_result creates an exclusive new directory and publishes metadata last.
Within a source/Git repository, existing MRI privacy rules require ignored output
trees. There is no pickle/object-array execution or dataset download.

Limits: metadata2MiB, at most32 arrays, at most5 dimensions, file64MiB and total
payload256MiB. Real boolean/integer/float dtypes up to8 bytes are allowed; domain
axes and fingerprints must match. NPY1/2 headers are bounded16KiB and declared
allocations/actual lengths are checked before loading. Legacy compressed archives
also enforce member identities and decompressed size/allocation limits.

Paths are artifact-relative arrays/NAME.npy. Traversal, absolute/URL references,
symlink components, nonregular files, excess size, invalid metadata/duplicate keys,
nonfinite values and bad hashes fail closed. POSIX directory-relative opens use
NOFOLLOW and bounded byte snapshots so verification and parsing use identical
bytes. macOS/Linux are the supported execution platforms; Windows is not claimed.

inspect_result reads bounded JSON only and reports integrity NOT_CHECKED; it does
not materialize/hash arrays. load_result and verify_integrity read complete linked
array snapshots, check file-byte and canonical content digests, validate finite
values, and return read-only arrays. Their work/memory is proportional to payload.
Explorer discovery currently performs full integrity verification before declaring
an artifact usable; benchmarks report that cost separately from metadata inspection.

Metadata SHA256 detects accidental edits, not malicious resealing. An attacker
controlling both payload and checksums can forge a new artifact; trusted signing
and external authenticated input provenance are separate unsolved concerns.
verify_provenance verifies only explicitly recorded relative input hashes under an
explicit input_root. Missing original hashes/evidence remain INDETERMINATE. Logical
identity, environment identity, numerical equivalence and byte identity are distinct.
Raw NIfTI/FIF/participant data remain external; this release serializes portable
numerical arrays and metadata, not a new medical image file format.
