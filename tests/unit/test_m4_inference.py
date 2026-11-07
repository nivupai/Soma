from dataclasses import replace

import numpy as np
import pytest

from soma.statistics.inference import InferenceConfig, infer_mean, robust_locations

CFG = InferenceConfig(n_resamples=399, seed=17)


def test_known_t_interval_and_basic_reflection():
    x = np.arange(1.0, 11)
    results = {r["method"]: r for r in infer_mean(x, cfg=CFG)}
    half_width = 2.2621571628540993 * np.sqrt(9.166666666666666 / 10)
    assert results["t"]["ci_low"] == pytest.approx(5.5 - half_width, abs=1e-9)
    assert results["t"]["ci_high"] == pytest.approx(5.5 + half_width, abs=1e-9)
    assert results["basic"]["ci_low"] == pytest.approx(11 - results["percentile"]["ci_high"])
    assert results["basic"]["ci_high"] == pytest.approx(11 - results["percentile"]["ci_low"])
    assert all(
        r["resampling_unit"] == "subject" and r["n_subjects"] == 10 for r in results.values()
    )


@pytest.mark.parametrize("scale,shift", [(1.0, 3.0), (2.0, 0.0), (0.001, 2.0), (-1.0, 0.0)])
def test_interval_translation_scale_metamorphisms(scale, shift):
    x = np.array([-0.4, 1.2, 0.3, 2.0, 1.1, 2.1, 0.6, 1.4])
    original = {r["method"]: r for r in infer_mean(x, cfg=CFG)}
    transformed = {r["method"]: r for r in infer_mean(x * scale + shift, cfg=CFG)}
    for method, row in original.items():
        other = transformed[method]
        assert row["status"] == other["status"] == "ok"
        expected = sorted([row["ci_low"] * scale + shift, row["ci_high"] * scale + shift])
        np.testing.assert_allclose([other["ci_low"], other["ci_high"]], expected, atol=1e-10)


@pytest.mark.parametrize(
    "x,status",
    [
        (np.array([]), "insufficient_subjects"),
        (np.array([1.0]), "insufficient_subjects"),
        (np.ones(10), "degenerate_zero_variance"),
    ],
)
def test_failed_methods_are_not_substituted(x, status):
    results = infer_mean(x, cfg=CFG)
    assert all(r["status"] == status for r in results)
    assert all(r["ci_low"] is None and r["ci_high"] is None for r in results)


def test_missingness_reproducibility_and_two_subject_studentization():
    x = np.array([0.0, 1.0, 2.0, np.nan, 3.0])
    a = infer_mean(x, cfg=CFG)
    assert a == infer_mean(x, cfg=CFG)
    assert all(r["n_subjects"] == 4 and r["n_missing"] == 1 for r in a)
    with pytest.raises(ValueError):
        infer_mean(x, cfg=replace(CFG, missing="raise"))
    result = infer_mean(np.array([0.0, 1.0]), methods=("studentized",), cfg=CFG)[0]
    assert result["status"] == "unreliable_studentized_standard_errors"
    assert result["invalid_pivot_fraction"] > 0.4
    assert result["ci_low"] is None


@pytest.mark.parametrize("values", [np.ones((2, 2)), np.array([0, np.inf]), np.array([1 + 2j, 0])])
def test_invalid_effects(values):
    with pytest.raises(ValueError):
        infer_mean(values, cfg=CFG)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_resamples": 99},
        {"seed": -1},
        {"confidence": 1},
        {"confidence": np.nan},
        {"max_invalid_studentized_fraction": 1},
        {"missing": "invent"},
    ],
)
def test_invalid_inference_config(kwargs):
    with pytest.raises(ValueError):
        InferenceConfig(**kwargs)


def test_robust_location_targets_do_not_hide_mean_contamination():
    x = np.r_[np.zeros(19), 100.0]
    result = robust_locations(x)
    assert result["mean"] == 5
    assert result["median"] == result["trimmed_mean"] == 0
    assert "differ" in result["target_note"]
    assert robust_locations(np.array([]))["mean"] is None
