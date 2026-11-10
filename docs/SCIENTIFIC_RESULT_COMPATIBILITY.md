# Scientific result compatibility

compare_results returns status COMPATIBLE, CONVERTIBLE, INCOMPATIBLE or
INDETERMINATE, plus field-specific issues, unknown fields and explicit left-to-right
unit factors. It validates metadata first. Compatibility concerns semantic meaning;
it does not assert equal numerical values, authenticated provenance or validity.

Comparison checks kind/quantity, dataset and subject identities, estimand, method
identity/version, parameters, temporal and spatial references, unit dimensions and
all domain declarations. These include EEG task/reference/windows, MRI grid and
ontology, source operators/conductivities/regularization and fMRI design/contrast/
noise/preprocessing/correction. Missing knowledge does not match a known null.
Legacy INDETERMINATE records cannot become comparable by agreeing on shape.

Examples rejected: EEG density vs BOLD effect; raw amplitude vs standardized effect;
execution vs imagery; another subject; RAS vs LPS; native vs template space;
different label ontologies; different contrasts, preprocessing or correction.
The engine is deliberately conservative about differing parameters. A valid
scientific between-method study needs an explicitly designed estimand, not a
permissive array comparator. Existing SDK require_comparable remains compatible
for its v0.16 metadata; use the new engine for versioned artifacts.

CONVERTIBLE means compatible physical dimensions have a recorded scale factor;
it never applies the conversion. convert_units implements only explicit V²↔uV²
PSD/wavelet-power conversions. It preserves axes, method, parameters and source
provenance, creates new array fingerprints, and requires new serialization/file
hashes. It rejects summary values whose unit semantics are not modeled. Other
conversions need a justified adapter or recomputation. Spatial frame/space changes
remain incompatible and require explicit existing transform/registration APIs.
