# ADR 0001: arrays inside numerical APIs, MNE at the EEG boundary

Status: accepted for Milestone 1.

MNE provides EDF ingestion and annotation semantics; NeuroDSP provides actual
spectral estimation. Soma adds input contracts, metadata and tests instead of
rewriting those libraries. The Signal class carries sampling and units without
a dependency on MNE, so numerical functions can serve future modalities. The
cost is deliberate explicit conversion at the dataset boundary and limited
third-party static typing. No generic imaging framework is introduced early.
