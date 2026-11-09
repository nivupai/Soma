"""Seeded independent-HRF BOLD simulation; descriptive task-vs-baseline contrast.

Expected positive and negative region means with positive variance. No human inference.
"""

import json

import numpy as np

from soma.sdk.fmri import Contrast, ModelConfig, contrast, fit
from soma.sdk.synthetic import simulate_fmri


def run():
    run, truth = simulate_fmri(seed=16042)
    fitted = fit(
        run, ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    )
    estimate = contrast(fitted, Contrast("task-effect", {"task": 1.0}))
    effect = np.asarray(estimate.maps["effect_size"].dataobj)
    positive = float(effect[truth["positive"]].mean())
    negative = float(effect[truth["negative"]].mean())
    assert positive > 0 and negative < 0
    assert not estimate.metadata["confirmatory_claim_allowed"]
    return {
        "positive_effect": positive,
        "negative_effect": negative,
        "policy": estimate.metadata["inference_policy"],
        "units": estimate.metadata["effect_units"],
        "residual_dof": estimate.metadata["residual_dof"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
