# MRI milestone implementation plan and acceptance criteria

Baseline: Soma 0.6.0, commit 8a5ca65, clean repository. This plan is recorded
before MRI implementation or real-image analysis. No participant EEG/MRI
coregistration will be invented and the fsaverage solver stays intact.

1. Extend physical frames without weakening existing metre/rigid contracts.
   Voxel coordinates are dimensionless and belong to identified grids. MRI
   volumes retain lazy data and metre-valued voxel-to-RAS geometry. Inspect both
   coded NIfTI affines and preserve explicit affine-selection provenance.
2. Implement one-pass pull resampling and SimpleITK RAS/LPS adapters. Registration
   returns fixed-to-moving physical transforms. Test known asymmetric phantoms,
   independent landmarks, translation/rotation, inverse consistency and failures.
3. Implement conservative mask/label processing and marching cubes in world
   coordinates, including orientation under negative affine determinants. Validate
   topology, quality and signed volume; fail closed for invalid/open meshes.
   Nested-shell readiness requires geometric containment, intersection and actual
   triangle separation checks, with explicit numerical tolerance and scope.
4. Build deterministic analytic phantoms and a real structural workflow, with
   deliberate transform recovery, threshold-mask limitations, measured geometry,
   ten scientific figure types, manifests and bounded-resource performance.
5. Add CLI/docs, retain baseline APIs/tests and verify source-model compatibility.

Acceptance thresholds are in physical units: affine round trips <1e-12 m on
well-conditioned synthetic grids; RAS/LPS and NiBabel/SimpleITK point agreement
<1e-10 m; identity resampling exact (nearest and linear); label resampling cannot
create labels; rigid phantom median landmark TRE <1 mm and rotation error <1°;
affine phantom median landmark TRE <1.5 mm. Thresholds apply only to the fixed
small perturbation benchmarks, not arbitrary image pairs. Poor overlap and
ambiguous images must be detected/reported rather than called successful anatomy.
Sphere meshes must be closed, consistently wound, Euler characteristic 2, with
area/volume errors decreasing across the tested resolutions. Open/duplicate/
nonmanifold surfaces cannot yield a reliable enclosed volume. Geometric nested
shell checks do not establish physiological conductor validity. Real MRI has no
reference tissue segmentation; no Dice score against invented labels is allowed.

The preferred SPM auditory structural image is available for personal education
and evaluation under its dataset terms (not the SPM software license). Fetch
only the anatomical member using HTTP ZIP byte ranges if supported; never fetch
the functional time series just to access the anatomy. Any availability or
licensing restriction is reported, not bypassed. No raw MRI enters Git.


## Recorded refinement after the binary-mask surface experiment

Binary sphere marching-cubes area errors were 7.7–8.6% over 4/3/2-mm grids and
were not monotonically convergent; these are retained as a failed binary-mask
convergence expectation. Add a continuous signed-distance sphere control to
separate voxelization bias from interpolation geometry. Its independent exact
area/volume comparisons test numerical convergence without reclassifying the
binary results as successful. This is an explanatory control added after that
finding, not a predeclared favorable result. Real foreground mesh failures are
also retained; no post hoc repair is used to claim anatomical/BEM validity.
