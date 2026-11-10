# Workflow publication, cancellation and recovery

Execution is serial, in topological order, after all required external inputs are
validated. Built-ins use fixed small synthetic dimensions and bounded algorithms.
Numeric arrays are finite real/bool, at most 64 MiB each/256 MiB per artifact, with
2 MiB JSON metadata. Live numerical payload checks enforce 256 MiB and release
values after their last consumer. Snapshot/serialization buffers and native library
allocations add memory beyond that payload limit; this is not an OS memory sandbox.

Each cache entry is built in a private sibling .building directory. All envelopes,
arrays and the stage receipt are validated, fsynced, and published by one directory
rename on the same filesystem. Files and directories are flushed before the parent
is fsynced. POSIX advisory locking serializes cooperating publishers; existing
published entries are never overwritten. Identical identities with conflicting
content fail. M17 standalone save_result retains its existing exclusive-directory
contract; the workflow layer adds atomic visibility around it.

Assumptions: trusted local Mac/Linux storage with POSIX directory rename/fsync and
cooperating writers. Unsupported/non-atomic filesystems, network mounts or hostile
concurrent filesystem mutation are not certified. Rename/fsync failure stops the
run; there is no copy fallback that would expose a partially complete entry.
Checksums provide integrity, not authentication against a malicious local operator.

Fault-injection tests cover before-stage, during-computation, partial serialization,
ENOSPC, before-publication, after-publication and before-status-update failures.
Unpublished staging is ignored; normal exceptions remove its temporary directory.
An abrupt process/power loss can leave ignored staging debris for manual cleanup.
A published entry is reverified on resume even if no completion journal exists.
Missing metadata, corrupted arrays/receipts, incompatible versions and changed
upstream identities cannot be accepted as old verified results. Corrupted published
entries remain unchanged and require an explicit operator decision outside resume.

Cancellation is cooperative at stage/publication boundaries; native calls are not
preempted. Run journals use existing atomic_json and may be updated; they are not
immutable result artifacts or validity authorities. If disk failure also prevents
journal writing, cache publication boundaries still determine recoverability.
Resume runs the same plan/verification logic, not journal shortcuts.

Scientific calls share a process-wide lock around the thread-limit context, so
cooperating SDK callers cannot race global numerical thread settings. Separate
processes may duplicate computation, but advisory publication locking and content
conflict checks protect committed entries; exactly-once computation is not promised.
Dry-run planning verifies cached entries against declared input fingerprints.
It explicitly labels external inputs as not freshly read; run/resume resolves and
snapshots every current input before any stage execution or reuse.
