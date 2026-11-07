#!/bin/sh
# Requires explicit sample cache and reports/milestone8-verified historical arrays.
set -eu
output_root=${1:-reports/milestone9-reproduction}
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1
export MPLCONFIGDIR=${MPLCONFIGDIR:-data/derived/.cache/matplotlib}
export XDG_CACHE_HOME=${XDG_CACHE_HOME:-data/derived/.cache}
soma source audit-coreg --dataset mne-sample --output "$output_root/coreg"
soma source audit-inverse --config configs/inverse-audit.yaml --output "$output_root/inverse"
soma source resolution-study --config configs/resolution-study.yaml --output "$output_root/resolution"
soma anatomy audit-evidence --config configs/anatomical-evidence.yaml --output "$output_root/evidence"
soma source uncertainty-study --config configs/uncertainty-study.yaml --output "$output_root/uncertainty"
