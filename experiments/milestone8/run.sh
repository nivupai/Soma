#!/bin/sh
# First explicitly fetch: soma anatomy inspect --dataset mne-sample --fetch
set -eu
output_root=${1:-reports/milestone8-reproduction}
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1
export MPLCONFIGDIR=${MPLCONFIGDIR:-data/derived/.cache/matplotlib}
export XDG_CACHE_HOME=${XDG_CACHE_HOME:-data/derived/.cache}
soma anatomy experiment synthetic --seed 42 --output "$output_root/synthetic"
soma anatomy coregister --config configs/coregistration.yaml --output "$output_root/coreg"
soma anatomy validate-bem --config configs/bem.yaml --output "$output_root/bem"
soma source build-individual --config configs/individual-source.yaml --output "$output_root/individual"
soma source uncertainty --config configs/source-uncertainty.yaml --output "$output_root/uncertainty"
soma source build-individual --config configs/individual-source.yaml --meg-fallback --output "$output_root/meg"
