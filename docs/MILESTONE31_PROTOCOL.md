# M31 frozen inverse-prior protocol

The machine-readable study design is `experiments/milestone31/design.json`, SHA256 `abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc`. This local pre-evaluation seal is not external preregistration. Prior M30 outcomes are known.

Six original heads, 72 original sources, and 24 independently seeded held-out sources are retained. Calibration source IDs 0–5 and test IDs 6–15 never overlap. All forward, prior, grid, noise, selection, uncertainty and failure rules are specified in the design. Nested union counts are [33, 173, 481]. Three priors and three regularization policies are crossed with Tikhonov, MNE and dSPM. Independent-repeat prediction tuning uses calibration sensor measurements only.

M30 post-merge CI run 44626578312 has 13/14 passing jobs: canonical PASS; changed native failure signature BLOCK_RELEASE. This baseline limitation is preserved; no M31 setting changes that policy. No M32 work is authorized.
