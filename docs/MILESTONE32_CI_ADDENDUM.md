# M32 initial CI release blocker

Initial published head 845cc4d1c578831d257347c2290ae0f2e6543e17, run
[44705359108](https://github.com/nivupai/Soma/actions/runs/44705359108), completes with
**13/14 jobs passing**. All four producers, the new MRI fixture, all older numerical
comparison families and canonical-mesh gate pass. The native Gmsh diagnostic correctly
returns **BLOCK_RELEASE**: its observed failure signature differs from the pinned
characterized discrepancy. It is not a permitted nonblocking finding under the current
policy, and this run is not relabeled as passing.

The original .02 relative/.01 V/(A·m) absolute elementwise comparator, policy signature,
original failure tables and all historical evidence remain unchanged. New findings are
separate in `ci-initial-native-diagnostic.json` and `ci-initial-native-failures.csv`.
Mac/Linux3.11 contrasts have 10/192 failures instead of 15; Mac/Linux3.12 retains 15;
Linux3.11/Linux3.12 has 16 failures instead of zero. Mac/Mac remains identical. Aggregate
relative differences around .4% do not replace or excuse elementwise failures.

Native cross-platform portability remains unestablished; no new root-cause resolution
or deterministic native mesh is claimed. Canonical fixed-mesh reproducibility does not
establish deterministic meshing. No policy, tolerance, sensor or source is changed.

An independent evidence-domain guard fix was already being validated before this CI
failure was observed. Its final head requires a new full CI run; that outcome must be
reported separately without erasing this blocked run. No M32 merge is authorized with
any required job failing, and no M33 work is started.
