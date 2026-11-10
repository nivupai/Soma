# Scientific provenance Explorer

The lazy-loaded Workflows page uses React Flow 12.12.1 after dependency inspection.
The package is about 1.2 MB unpacked, with Zustand/classcat/xyflow-system dependencies;
the built workflow view is about 189 kB / 62 kB gzip. It is separate from the
existing EEG/MRI/source/fMRI bundles. Existing Source chunk-size warning remains.
The library's [accessibility documentation](https://reactflow.dev/learn/advanced-use/accessibility)
and [component reference](https://reactflow.dev/api-reference/react-flow) informed
keyboard selection and view controls. Retained attribution and MIT licensing apply.

Rounded artifact nodes and rectangular stages use directional edges. Select with
mouse or the keyboard node navigator; choose upstream ancestry/downstream impact,
filter nodes, zoom/pan, use minimap and fit-to-view. A compact four-column layout
keeps small workflows readable; large DAGs use viewport rendering and node search.
Selected metadata shows implementation/parameters, scientific identity, validation,
recorded cache status, runtime, failure reason and limitations. Saved invalidation
reports and software environment are inspectable separately.

GET /api/workflows lists the four unexecuted synthetic descriptions and explicitly
registered workflow resources. GET /api/workflows/ID projects bounded graph/run
metadata; GET /api/workflows/ID/lineage/NODE queries ancestry or downstream impact.
No route submits or launches a workflow. Rendering does not read cache arrays.
Saved cache observations are labeled RECORDED and require fresh CLI verification.

Local graphs/run journals require an explicit registry entry of kind workflow under
an allowed root. References are rechecked on every request. Redacted exports drop
private root/path/credential fields and absolute-location strings. Subject identities
must be explicit keyed pseudonyms; the secret is never recorded. Pseudonyms and
hashes are not anonymization. Dataset-use restrictions/limitations are retained.
Do not commit private run records or participant artifacts. Synthetic screenshot
inspection stays in ignored reports; no new binary is added to Git.
