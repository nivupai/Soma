# Workflow CI and packaging verification

Milestone 18 extends the existing 13-job scientific SDK workflow rather than
replacing its gates. Python3.11/3.12 scientific, distribution, quality, security,
Explorer, feasible dependency-floor and four actual platform reproducibility lanes
remain. The platform lanes additionally execute workflow adversarial tests and
all four cold/warm/invalidation replays. The comparison job verifies both the
unchanged M17 oracle outputs and new workflow summaries/identity observations.
Private synthetic-only artifacts have 14-day retention; durable aggregate evidence
is stored in experiments/milestone18 after inspecting actual reports.

Frontend tests, installed API browser tests, TypeScript, ESLint, Prettier, production
build and npm audit remain mandatory. Core packaging tests install wheel, sdist and
source noneditably outside the checkout; ten public SDK examples include the
workflow demonstration. Repeated builds verify byte reproducibility. Strict mypy,
Ruff, pip check, dependency audit and full sanitized-history Gitleaks checks remain.
No new secret-scanner suppression or data exception is introduced.

Local full pytest includes explicitly cached integration data. Demo-only CI omits
the existing local-data integration lane/browser test; this remains a documented
scope limit, not a claim to human-data verification on GitHub runners. Changes go
through feature/milestone18-provenance-dag and a private green PR; never force-push,
rewrite published history or merge failing checks. No PyPI release is performed.

## Protocol matrix (0.19.0 addendum)

The existing 13 jobs are retained. The four actual macOS arm64/Linux x86_64 Python
3.11/3.12 jobs additionally run protocol tests and all four controlled demonstrations.
They upload `protocol-replay.json` with actual environment evidence. The dependent
comparison job requires all four platforms and compares against frozen protocol
bounds without widening; records exact agreement separately. Existing M17/M18
oracles remain required. Explorer CI explicitly prepares synthetic histories before
browser testing; GET requests never create histories.
