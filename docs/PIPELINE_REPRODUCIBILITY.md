# Pipeline identity, execution and recovery

Each stage declares artifact types, dependencies, RAS metre semantics, software,
parameters and failure rules. Missing dependencies, cycles and duplicate outputs
are rejected before execution. The serial DAG executes invalid inputs no further
than their first failing stage; run.json preserves stage/error and intermediate
committed caches for explicit recovery. No distributed scheduler is introduced.

StageCache reuses Soma's cached_object, fingerprint, SHA256 and atomic_json.
Keys bind input content/geometry, configuration, subject/session, transform grids,
backend implementation/cache_version, Soma source tree and dependency versions.
JSON keys are canonicalized before identity comparison, avoiding integer-label
mapping mismatches after serialization. Arrays are pickle-free. Unchanged volumes
are aliases to upstream artifacts, so disabled processing does not duplicate MRI
arrays at each stage. Whole-source invalidation is conservative, not maximally
fine-grained. External adapters must update cache_version whenever dependencies,
model weights or relevant runtime implementation change; no silent weight fetch.

New output/report roots refuse collisions. Identical completed `resume=True` verifies
derivative/description hashes and reuses final outputs without reading stage caches;
that is recorded as verified output reuse, not eleven fictitious cache reads.
A new output with compatible stage inputs exercises actual stage cache hits.
Interrupted work resumes committed stages. A missing half-publication may be
quarantined under explicit resume; committed corruption fails unless repair_cache
is explicitly enabled. Quarantine/rebuild is logged and never repairs source MRI.
Published anatomy is exclusive/atomic. Recovery after publication verifies the
same run identity, arrays, geometry, metadata and tissue LUT before accepting it.

Keep all native/private images, cache arrays, source paths and subject records
under ignored data/derived, reports or derivatives locations. The output guard
rejects tracked source-tree destinations and writes inside original datasets
(except a genuine BIDS derivatives subtree). No original clinical metadata or
images are committed. Source inputs are rehashed for resume and original benchmark
reports/seals remain unchanged. Set OPENBLAS_NUM_THREADS=1 and
ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1 for the recorded runs; stages execute serially.

The prespecified baseline-preserving config is configs/mri-pipeline.yaml; separate
N4/mask/grid/surface settings define a new experiment. configs/milestone12-freeze.json
seals the decision record and benchmark configs before processing. Prior inspected
human labels cannot be used to claim a new independently tuned holdout result.
Optional full BIDS validation uses an installed official local bundle and local
schema with network denied. CI tests use generated synthetic images, no downloads
or machine-specific speed assertions. Cached human/template integrations remain
opt-in. See experiments/milestone12 for explicit benchmark/recovery reproduction.
