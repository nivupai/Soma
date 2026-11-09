# BIDS ingestion

Soma0.12 uses PyBIDS0.22 for genuine raw BIDS datasets. `inspect_bids` checks dataset
description, indexes subject/session/anatomical entities, inherits JSON metadata
through PyBIDS, and discovers derivative dataset descriptions. It never writes
into the input. `select_bids` accepts requested participant/session and entity
filters; multiple matches fail unless `first-sorted` is explicit. No averaging,
implicit registration or contrast substitution occurs. T1w is the supported input.

Dataset description must identify a raw dataset with Name/BIDSVersion. Filename
validation uses the established Python BIDS validator and entity consistency
checks; this is indexing/selection validation, not complete BIDS certification.
The optional full validator is the official bids-validator-deno3.0.2 bundle using
a local BIDS1.11.2 schema from bidsschematools2.0.1. Its Deno invocation has no
network permission; no MRI uploads or remote schema retrieval occurs at validation.
Package version is recorded explicitly (self-reported Git-derived versions can
be misleading when invoked inside another checkout). All warnings/errors are saved.

Legacy IBSR/MRBrainS inputs reuse native loaders, ontology rules and permission
checks. They are `legacy` InputRecords, not original BIDS datasets. IBSR bridge
selection works without MRBrainS installed; MRBrainS requires its local Readme/
manifest and uses only the labeled TRAINING partition. Original coded identities,
conversion assumptions and content fingerprints remain in private receipts.
Standalone NIfTIs may use explicit standalone records, never be claimed original
BIDS by default. Legacy output entities are Soma-assigned alphanumeric labels;
that naming is not anonymization. No raw staging layout is misrepresented as BIDS.

```python
from pathlib import Path
from soma.pipeline.ingestion import select_bids
from soma.pipeline.engine import configuration, run_pipeline

record = select_bids(Path("/local/bids"), "01", session="A")
plan = run_pipeline(
    record,
    configuration(Path("configs/mri-pipeline.yaml")),
    Path("derivatives/soma"),
    report_root=Path("reports/mri"),
    dry_run=True,
)
```

For unambiguous non-default acquisitions use `filters={'run':2}` in Python or the
documented explicit first-sorted policy in CLI. Dry runs list contracts/dependencies
without cache/output writes and do not certify input intensities. Dataset-wide
inspection may index metadata across subjects; execution uses the selected image.

## Milestone14 addendum: legacy functional sources and external derivatives

The ds000114v1.0.2 source advertises BIDS1.0.0rc2. New discovery deliberately indexes
it without claiming current BIDS validation. External fMRIPrep outputs require
GeneratedBy/version, resolvable source dataset relationships, explicit space/mask,
confound metadata, T1 sources, transforms and reviewed QC. Metadata consistency and
numerical geometry are separately labeled; filename patterns do not establish
preprocessing or anatomy. No new statistical suffix or original-BIDS staging claim
is introduced. Baseline official schema tests remain operational. See
[preprocessing audit](FMIRI_PREPROCESSING_AUDIT.md).
