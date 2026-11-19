# Canonical-mesh v1 evidence

Actual four-runner results from run44425538067 at implementation commit41e528d.
The outer protocol and exact physical-input fingerprints identify the new v1
experiment independently of the original frozen native M30 protocol.

Canonical: PASS, all192 entries on each actual platform, unchanged rtol0.02 and
atol0.01 V/(A m). Native: FAIL at the original unchanged comparator. Both fields
are retained under each platform folder. These numerical reports are not
platform-specific expected values and are not read by the computation.

The canonical maximum relative difference is1.1170034248281651e-14 and maximum
absolute difference2.9416469260468148e-12 V/(A m), with zero failed entries.
This fixed homogeneous mesh check does not establish deterministic native
Gmsh meshing, four-tissue accuracy or human anatomical validation.

Both M28 and M29 were already merged by the owner and have separately verified
13/13 post-merge push checks. PR15 targets main and remains unmerged. No release
gate decision or merge approval is implied by this archive. Later evidence-only
commits preserve this run as historical evidence; final exact-head status is
reported in the PR completion record. No M31 work is started.
