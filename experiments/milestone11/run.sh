#!/bin/sh
# Explicit prerequisite: authorized SCI archives/selected files in data/raw/references/sci-head.
# No implicit network calls, model installations, or registered-data access.
set -eu
output_root=${1:-reports/milestone11-reproduction}
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1
export MPLCONFIGDIR=${MPLCONFIGDIR:-data/derived/.cache/matplotlib}
export XDG_CACHE_HOME=${XDG_CACHE_HOME:-data/derived/.cache}
mkdir -p "$(dirname "$output_root")"
mkdir "$output_root"
soma mri references inspect --dataset sci-head > "$output_root/reference-inspection.json"
soma mri benchmark-tissues --config configs/tissue-benchmark.yaml --output "$output_root/tissues"
soma anatomy compare-conductors --config configs/conductor-comparison.yaml --output "$output_root/conductors"
soma source priors --config configs/source-priors.yaml --output "$output_root/priors"
soma source grid-priors --config configs/grid-priors.yaml --output "$output_root/grid-priors"
soma experiments anatomical-holdout --config configs/anatomical-holdout.yaml --output "$output_root/holdout"
python -c 'import json; from soma.validation.mne_equivalence import uniform_mne_agreement; print(json.dumps([uniform_mne_agreement(x) for x in (.01,1/9,1)],indent=2))' > "$output_root/MNE-equivalence.json"
