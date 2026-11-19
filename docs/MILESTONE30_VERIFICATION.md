# M30 verification addendum

M30 branches from verified M29 head88fcda2f2d4fd4f215294fac966fa180a6594df9, with
PR14 targeting M28 PR13. Both remain unmerged. The new PR targets the M29 feature
branch until predecessors safely merge. No force push, history rewrite, security
exception or branch-protection change is used. Main remains the verified predecessor.

The physical design/M19 seal is committed before final numerical outcomes. Gmsh
pilot fields, grid containment and resource counts precede that seal; no localization
accuracy was inspected to select grids. Native Gmsh is independent of the existing
radial mesher, while FEM assembly is deliberately reused. Executed source modules
are archived with unique relative-path names and hashes before the study starts.
M28/M29 artifacts, protected historical files and46 M24 archive files remain immutable.

The full experiment stays outside ordinary CI. Small adversarial source/grid/mesh
checks and a native Gmsh homogeneous control run in the actual four-platform matrix.
The13-job workflow retains all12 prior comparison families and adds a thirteenth
with its prespecified native-mesher tolerance and strict grid/volume checks. The
main10% physical engineering target is unchanged. Actual platform bundles are
independently downloaded and every comparison family rerun locally.

Run full/offline Python suites, frontend/type/lint/format/build and configured
Playwright; Ruff/format; strict mypy; dependency checks and full security audits;
reproducible wheel/sdist builds; three fresh noneditable core/Explorer installations
with22 SDK examples and payload equality. Optional mesher/FEM physical checks are
run in an installed wheel as well as the source environment. Final figures and
Explorer output are visually inspected. Actual counts, hashes and receipts appear
in `experiments/milestone30/verification.json` and the dependent PR completion record.

Public/history privacy scans retain unchanged Gitleaks rules and exact reviewed
historical false positives. Raw clinical data, credentials, local interpreter paths,
restricted assets and model weights are excluded. Raw child logs/packets remain
ignored; public failures retain numerical diagnoses without private path strings.
All .gitignore protections remain enabled.

The full npm audit remains a required gate. If GHSA-fc5q-39xc-vjpf remains unresolved,
M30 and its predecessors remain unmerged. Passing Python/privacy checks is not a
passing npm audit. Postmerge CI is recorded only after an actual authorized merge;
otherwise its status is NOT_PERFORMED. Milestone31 is not started.
