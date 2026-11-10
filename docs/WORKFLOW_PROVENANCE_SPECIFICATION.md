# Workflow provenance specification

Soma 0.18.0 introduces opt-in `soma.workflow/1.0.0` descriptions, separate from
unchanged soma.result envelopes 1.0.0/1.1.0. Artifacts and computation stages have
separate stable opaque IDs. Input ports point to artifacts; output artifacts name
exactly one producer. Multiple consumers and multiple output ports are supported.
No ID depends on a memory address or filename. Graphs are bounded to 5,000 nodes,
20,000 edges and the existing 2 MiB metadata reader for saved descriptions.

The typed frozen dataclasses Artifact, Stage and Graph define the public SDK.
Execution snapshots nested declarations. Graph validation checks IDs, producers,
references, cycles, duplicates, type/port contracts, explicit scientific metadata,
registered implementations/versions, seeds, units, coordinates and policy gates.
Ordering delegates to existing pipeline.contracts.ordered_graph. The serializer
reuses pipeline.cache.encode/decode and M17 bounded nonpickle result IO; the serial
scheduler and atomic-directory pattern extend existing Soma orchestration rather
than introducing a distributed dependency system. An inventory of actual legacy
systems is in experiments/milestone18/infrastructure-inventory.json.

Each output is an integrity-checked experiment.manifest envelope. Workflow-specific
typed scientific metadata and producer/input identities live in provenance.workflow;
array data remain linked bounded NPY files. No new result kind or estimator was
introduced. `Artifact.validation` declares the required numerical validation
policy, not proof that a planned output already exists. Actual validation state
comes from a verified execution/cache observation. Format/lineage verification is
not anatomical, statistical or clinical certification.

Graph.lineage supports upstream ancestry and downstream impact, including node
and edge IDs; declarations expose parameters, dataset identity, software and
limitations. Executor.plan reports exact key components and verified hits/misses.
Run records retain cache observations, runtimes, environment, content hashes and
optional before/after invalidation explanations. Journals are observations only.

The CLI permits only explicitly registered built-in stages. It never imports
module names or executes commands from a description. SDK Registry/Operation
registration is code-owned, requires explicit ports/versions and disallows captured
closures. Custom Python registration is trusted operator code, not an execution
sandbox; undeclared mutable global state is unsupported.

Existing MRI eleven-stage orchestration, cohort processing and historical caches
are preserved. Their older receipts do not establish all new lineage/environment
contracts, so they are not automatically imported or treated as verified hits.
The representative workflows reuse existing numerical functions explicitly.
