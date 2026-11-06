import numpy as np
import pandas as pd
import pytest

from soma.statistics.hierarchical import (
    ResamplingConfig,
    holm,
    lateralization_contrasts,
    population_summary,
    sign_flip_pvalue,
    subject_bootstrap,
    subject_contrasts,
)


def feature_fixture():
    rows = []
    # Subject 1 has many trials; subject 2 has one. They must retain equal subject weight.
    for subject, left, right, trials in ((1, 4.0, 1.0, 40), (2, 1.0, 2.0, 1)):
        for run in (4, 8):
            for condition, value in (("left hand imagery", left), ("right hand imagery", right)):
                for channel in ("C3", "C4"):
                    for _ in range(trials):
                        rows.append(
                            dict(
                                subject=subject,
                                run=run,
                                channel=channel,
                                band="mu",
                                condition=condition,
                                kind="imagery",
                                absolute_power_v2=value,
                                erd_percent=100 * (value - 1),
                                log_power_ratio=np.log(value),
                            )
                        )
    return pd.DataFrame(rows)


def test_pair_runs_before_equal_subject_resampling():
    runs, subjects = subject_contrasts(feature_fixture())
    selected = subjects[(subjects.channel == "C3") & (subjects.outcome == "absolute_power_v2")]
    np.testing.assert_allclose(selected.sort_values("subject").contrast, [3.0, -1.0])
    assert (selected.n_runs == 2).all()
    result = subject_bootstrap(selected.contrast.to_numpy(float))
    assert result["estimate"] == 1  # not trial-count-weighted ~2.9
    assert len(runs) == 32


def test_missing_run_pair_is_not_filled_or_unpaired():
    table = feature_fixture()
    table = table[
        ~((table.subject == 1) & (table.run == 8) & (table.condition == "right hand imagery"))
    ]
    runs, subjects = subject_contrasts(table)
    selected = subjects[(subjects.subject == 1) & (subjects.outcome == "absolute_power_v2")]
    assert (selected.n_runs == 1).all()
    assert (selected.contrast == 3).all()
    assert runs[(runs.subject == 1) & (runs.run == 8)].contrast.isna().all()


@pytest.mark.parametrize(
    "values",
    [np.array([]), np.array([2.0]), np.array([2.0, 2.0, 2.0]), np.array([-2.0, 0.0, 3.0, 4.0])],
)
def test_bootstrap_determinism_and_effective_n(values):
    a = subject_bootstrap(values)
    assert a == subject_bootstrap(values)
    assert a["n_subjects"] == len(values)
    if len(values) < 2:
        assert a["ci_low"] is None and a["ci_high"] is None
    elif np.ptp(values) == 0:
        assert a["ci_low"] == a["ci_high"] == values[0]
    else:
        assert a["ci_low"] <= a["estimate"] <= a["ci_high"]


@pytest.mark.parametrize("values", [np.array([np.nan]), np.array([np.inf]), np.ones((2, 2))])
def test_invalid_bootstrap(values):
    with pytest.raises(ValueError):
        subject_bootstrap(values)


def test_sign_flip_exact_resolution_and_holm():
    assert sign_flip_pvalue(np.ones(5)) == pytest.approx(2 / 32)
    np.testing.assert_allclose(holm(np.array([0.01, 0.04, 0.03])), [0.03, 0.06, 0.06])
    assert sign_flip_pvalue(np.array([1.0, -1.0, 1.0, -1.0])) == 1
    for values in (np.array([np.nan, 0.1]), np.array([1.0]), np.ones((2, 2))):
        with pytest.raises(ValueError):
            sign_flip_pvalue(values)
    with pytest.raises(ValueError):
        holm(np.array([1.1]))


def test_population_exclusions_and_duplicate_subject_safeguard():
    _, subjects = subject_contrasts(feature_fixture())
    summary, leave_out = population_summary(subjects, ResamplingConfig(sign_flip=True))
    assert (summary.n_subjects == 2).all()
    assert summary.p_holm.notna().all()
    assert len(leave_out) == len(summary) * 2
    with pytest.raises(ValueError, match="One contrast per subject"):
        population_summary(pd.concat([subjects, subjects]))


def test_lateralization_sign_and_interaction():
    df = feature_fixture()
    df.loc[(df.condition == "left hand imagery") & (df.channel == "C4"), "absolute_power_v2"] *= 0.5
    df.loc[(df.condition == "right hand imagery") & (df.channel == "C3"), "absolute_power_v2"] *= (
        0.5
    )
    lateral = lateralization_contrasts(df)
    assert (lateral[lateral.metric == "left_log_contra_over_ipsi"].value < 0).all()
    assert (lateral[lateral.metric == "right_log_contra_over_ipsi"].value < 0).all()
    assert (lateral[lateral.metric == "log_condition_by_sensor_interaction"].value < 0).all()


def test_resampling_configuration_validation():
    for kwargs in ({"n_bootstrap": 99}, {"confidence": 0}, {"confidence": 1}):
        with pytest.raises(ValueError):
            ResamplingConfig(**kwargs)


@pytest.mark.parametrize("scale", [1e-20, 1.0, 1e20])
def test_sign_flip_is_invariant_to_power_units(scale):
    assert sign_flip_pvalue(np.ones(5) * scale) == pytest.approx(2 / 32)
