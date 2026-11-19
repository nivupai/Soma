# Canonical-mesh reproducibility experiment v1

This is a separately versioned, post-outcome numerical control requested after the
M30 native Gmsh investigation. Its protocol is configs/canonical-mesh-v1.json.
The previously serialized synthetic fixture is unchanged and fingerprint-verified;
no platform is allowed to regenerate or repair it. Previous shared-mesh diagnostic
outcomes were already known, so this is not external preregistration or independent
confirmation of an unobserved hypothesis.

The experiment loads identical vertices, positive tetrahedral connectivity, material
labels, surface facets, source positions and sensor positions on all four actual
Linux x86_64/macOS arm64 Python3.11/3.12 runners. Exact float64/int64 array
fingerprints and the fixture's byte SHA256 are verified. Existing scikit-fem full
subtraction, q8 quadrature, insulating boundary, average reference and source-major
XYZ order are used. This homogeneous control retains four labels with all
conductivities0.33 S/m,212 nodes,1072 tetrahedra,2 sources and32 sensors. It is not
four-tissue conductivity accuracy or human anatomical validation.

The outer result identity and protocol fingerprint are canonical-mesh-v1-specific.
A compatibility envelope is adapted in a temporary directory and passed through
the original unchanged scripts/compare_mesh_grids.py comparator. All192 field
entries retain rtol0.02 and atol0.01 V/(A m), together with its existing geometry,
quality, reference-accuracy and environment-coverage requirements. Additional
canonical checks enforce exact physical-input identity. No platform-specific
expected fields or aggregate-only substitute is used.

The native runner, original comparator and original failing reports remain
unchanged. A distinct CI job compares the new canonical results independently of
the native comparison job; the native failed gate is still executed and reported.
The workflow therefore gains a fourteenth job, not a tolerance exception. Both
old and new outcomes must be reported. Fixed-mesh reproducibility does not imply
deterministic Gmsh generation, nonspherical accuracy or source-localization accuracy.

Native Gmsh meshes differed even on serialized boundary inputs. Official source
and runtime probes expose nonportable random sequences and native geometric
operations; a unique internal cause remains unproven. All bounded supported-option
controls and their failed entries remain in the preceding investigation artifacts.
No frozen M30 protocol or historical numerical measurement is amended.

No M30 merge is authorized by this experiment. A valid explicit release-gate
decision and user approval are required even if the canonical comparison passes.
The npm audit remains enabled. M31 is not started.
