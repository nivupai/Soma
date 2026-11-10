# Research protocol and replay design contract

Semantics frozen before implementation for Soma 0.19.0. A protocol declares a
scientific question, descriptive objective/estimand, population and independent
sampling unit, eligibility/exclusions, conditions, preprocessing/methods, primary
outcomes, inference/correction, sensitivity/QC rules and limitations. Every stage
binds a named protocol requirement. Protocol identity differs from graph/cache,
dataset snapshot, environment and execution identities.

Initial schema soma.protocol/1.0.0 is strict finite canonical JSON. A local seal
binds the complete document and validation receipt; scientific identity excludes
editorial/optional annotations and version labels. Sealed objects expose copies,
never mutable internal mappings. Exclusive serialization never overwrites a seal.
Hash evidence is not independent preregistration, authorship or verified timing.
Historical adapters preserve inspected evidence and remain INDETERMINATE where
required scientific/execution metadata is absent. No historical file is rewritten.

EXACT requires identical protocol/content and exact actual M18 environment evidence;
byte, numeric identity and bounded numeric equivalence are separate observations.
CONTROLLED permits only prespecified snapshot/unit/session/platform differences,
unchanged scientific intent and stage semantics, and frozen equivalence bounds for
matching inputs. Different input data produce descriptive outcome differences,
not a numerical reproducibility verdict. EXPLORATORY requires an explicit new
amendment and never grants confirmation. All replay results remain descriptive.

Population/preprocessing/contrast/estimand/inference/anatomical/implementation
changes are structural scientific amendments regardless of version text. Editorial
and optional annotations cannot change the scientific fingerprint. No tolerance
widening after outcomes. Missing evidence and incomplete/QC-excluded units remain
visible; no favorable subset is silently selected. Sequence is explicit and does
not infer human longitudinal order from file names. Initial execution support is
bounded synthetic workflows; human session/permission verification is not invented.
