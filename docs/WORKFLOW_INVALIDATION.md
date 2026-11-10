# Dependency-aware invalidation

`invalidation(before, after)` validates both DAGs, identifies changed declarations
and traverses descendants. Reports name changed fields, direct causes and affected
nodes. `soma workflow explain-cache CURRENT --previous PREVIOUS --cache-root ROOT`
combines that report with actual verified cache decisions. A missing exact key is
an explicit miss; it is never evidence that a similarly named result is reusable.

Executed synthetic examples:

| Change | Recomputed stages | Reused stages |
|---|---|---|
| EEG average reference to none | reference, PSD, bands | generation, recording validation |
| MRI threshold 1.0 to 1.2 | segmentation, QC, surface | generation, geometry, bounded N4 |
| fMRI task contrast weight 1 to 2 | contrast, ROI | BOLD generation/validation, design, fitted OLS statistics |
| Toy forward scale 1 to 1.2 | forward, inverse, reconstruction/resolution | geometry |

Input fingerprints include voxel geometry, so geometry changes propagate to all
consumers. Frame mismatches are rejected: no implicit transform stage is registered.
Native unit and ontology contracts are checked. The binary threshold example cannot
be relabeled as a tissue segmentation by changing metadata. Changing a declared
ontology invalidates lineage, and unsupported tissue reinterpretation is rejected.
Seed/stream, precision, dependencies, model configuration and numerically relevant
settings enter identity. Palette/layout preferences are separate and excluded.

INDETERMINATE scientific declarations or validation are insufficient for reuse.
Environment differences conservatively miss. Corruption is a verification failure,
not an ordinary cache miss and not permission to repair a published artifact.
