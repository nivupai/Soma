# Soma Explorer local security and privacy

This is a local research application. Both services bind127.0.0.1 by default.
No public hosting, external access, analytics or telemetry exporter is configured.
It is not an authenticated multi-user or internet-facing deployment.

Only explicit server-side resource IDs are accepted. An ignored JSON allowlist
names dataset roots and root-relative files. Browser-supplied paths, directory
listing, uploads, arbitrary code and shell execution are absent. Resolution rejects
absolute relative-resource names, `..`, symlink escapes, unknown identities and
wrong resource kinds. Paths are rechecked even when numerical data are cached.
File signature changes invalidate dataset caches; state resets prevent reuse of
unrelated browser selections. Operator declarations of participant/frame identity
must still be scientifically reviewed; path safety is not anatomical validation.

Trusted hosts are localhost/127.0.0.1, and CORS permits only the documented local
ports8000/5173. Unexpected/null Origin and cross-site fetch metadata are rejected,
as are rebinding Host names. Requests are capped16KiB, including streamed request
bodies. Responses are no-store/nosniff and have restrictive content policies.
Frontend assets use a self-only CSP (local Vite websocket excepted), system fonts
and no third-party network resources. A local process running under the same user
can access the service; there is no authentication barrier against that process.
Do not expose these ports through a tunnel or public reverse proxy.

Raw MRI/EEG and derived participant images remain under ignored data/derivative
roots. The browser receives bounded scientific data because the operator has
explicitly selected local resources; this is not anonymization. HTTP/scientific
errors do not reveal local paths. Historical receipt exports remove path-bearing
fields and strings; scientific source metrics and all rows within the metadata
size cap are preserved. React renders text, never supplied HTML. Exports are sanitized
and CSV cells are protected against formula prefixes. Only configured PNG figures
with verified type/size can be served; there is no general file endpoint.

One worker and a two-job capacity bound background work. Only the fixed EEG
analysis request is accepted, no executable payload. Unique UUID manifests are
written atomically to ignored `data/derived/explorer/jobs`; failures and cancelled
jobs do not publish successful results. Cancellation waits for the current bounded
native operation to return. Small synchronous EEG analyses additionally have a
bounded capacity. This is not an OS/container sandbox for arbitrary workloads;
arbitrary workloads are not accepted.

Tests cover traversal, encoded unknown paths, symlink mutation after caching,
CORS/Host rejection, payload limits, prohibited execution kinds, unknown units,
misaligned segmentation, sealed source hashes, changed-file invalidation,
comparison incompatibility and inference-policy refusal. No API exposes a
confirmatory inference bypass. No raw patient image, local allowlist, participant
screenshot or individual job manifest is staged in Git.
