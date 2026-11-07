#!/bin/sh
# Explicit prerequisite: soma mri references fetch --dataset brainweb
# Explicit prerequisite: soma mri references fetch --dataset mindboggle-101
# Conditional participant example additionally needs the previously cached sample.
set -eu
output_root=${1:-reports/milestone10-reproduction}
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1
export MPLCONFIGDIR=${MPLCONFIGDIR:-data/derived/.cache/matplotlib}
export XDG_CACHE_HOME=${XDG_CACHE_HOME:-data/derived/.cache}
soma mri references list
soma mri benchmark-segmentation --config configs/segmentation-benchmark.yaml --output "$output_root/segmentation"
soma mri benchmark-surfaces --config configs/surface-benchmark.yaml --output "$output_root/surfaces"
soma anatomy repair-audit --config configs/mesh-repair.yaml --output "$output_root/repair"
soma source offgrid --config configs/offgrid.yaml --output "$output_root/offgrid"
soma source grid-convergence --config configs/grid-convergence.yaml --output "$output_root/grid"
python experiments/milestone10/interaction_analysis.py "$output_root/offgrid" "$output_root/discretization-regularization.json"
