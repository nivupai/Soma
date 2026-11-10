# Protocol versioning

Schema `soma.protocol/1.0.0` is separate from Soma 0.19.0 and each study's version.
Full identity hashes canonical finite JSON. Scientific identity includes the study
ID, scientific declarations, executable requirements, replay policy and tolerances;
it excludes version labels, editorial notes, optional metadata and unverified
registration references. Version strings alone never authorize compatibility.

| Difference | Required action |
| --- | --- |
| Identical declaration | No revision |
| Editorial/optional annotation | Increasing compatible version and explicit parent amendment for controlled replay |
| Execution CPU/resources | Execution record only, provided scientific settings and exact environment policy still hold |
| Dataset snapshot/additions/session | New snapshot/execution; only prespecified controlled axes |
| Population/eligibility/estimand/primary contrast | Increasing major revision, explicit amendment, exploratory study |
| Preprocessing/reference/HRF/noise/ontology/anatomical conventions | Increasing major revision and exploratory study |
| Inference/correction/tolerance/seed-policy changes | Increasing major revision and exploratory study |
| Algorithm implementation | Implementation drift; replay rejected without a future explicit compatibility adapter |

`compare_protocols` compares structure, not just semantic version labels. A method
change labeled 1.0.1 is invalid. `amend` records the parent fingerprint, reason,
authorization reference and outcome-inspection declaration. Timing is always
`LOCAL_UNVERIFIED`; saying outcomes were not inspected is not independent proof.
No amendment automatically preserves confirmation or prospective status.
