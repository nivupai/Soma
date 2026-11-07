"""Subject-mean intervals with explicit assumptions and failures; no method fallback."""

import warnings
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import stats

METHODS = ("percentile", "basic", "studentized", "bca", "t")


@dataclass(frozen=True)
class InferenceConfig:
    confidence: float = 0.95
    n_resamples: int = 1999
    seed: int = 42
    max_invalid_studentized_fraction: float = 0.05
    missing: str = "omit_with_counts"

    def __post_init__(self) -> None:
        if (
            not np.isfinite(self.confidence)
            or not 0 < self.confidence < 1
            or not isinstance(self.n_resamples, int)
            or self.n_resamples < 100
            or not isinstance(self.seed, int)
            or self.seed < 0
            or not 0 <= self.max_invalid_studentized_fraction < 1
            or self.missing not in ("omit_with_counts", "raise")
        ):
            raise ValueError(
                "Invalid confidence, bootstrap count, seed, missing policy or invalid-pivot limit"
            )


DEFAULT_INFERENCE = InferenceConfig()


def _mean_se(values: NDArray[np.float64], axis: int = -1) -> NDArray[np.float64]:
    return np.stack(
        (
            np.mean(values, axis=axis),
            np.std(values, axis=axis, ddof=1) / np.sqrt(values.shape[axis]),
        )
    )


def infer_mean(
    values: NDArray[np.float64],
    methods: tuple[str, ...] = METHODS,
    cfg: InferenceConfig = DEFAULT_INFERENCE,
) -> list[dict[str, Any]]:
    """One finite/NaN entry per independent subject; missingness is counted.

    SciPy supplies bootstrap resampling, BCa jackknife adjustment, and Student t
    quantiles. The mean's analytic SE supports the studentized bootstrap pivot.
    Infinite/complex values are invalid, not missing observations.
    """
    if not methods or len(set(methods)) != len(methods) or set(methods) - set(METHODS):
        raise ValueError("Choose unique supported inference methods")
    if np.iscomplexobj(values):
        raise ValueError("Subject effects must be real")
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or np.isinf(x).any():
        raise ValueError("Inference requires a 1D vector without infinite values")
    missing = int(np.isnan(x).sum())
    if missing and cfg.missing == "raise":
        raise ValueError("Missing subjects are forbidden by this configuration")
    x = x[~np.isnan(x)]
    n = len(x)
    estimate = float(np.mean(x)) if n else None
    sd = float(np.std(x, ddof=1)) if n > 1 else None
    se = sd / np.sqrt(n) if sd is not None else None
    base = {
        "estimand": "equal-subject arithmetic mean paired contrast",
        "resampling_unit": "subject",
        "n_subjects": n,
        "n_requested": n + missing,
        "n_missing": missing,
        "estimate": estimate,
        "subject_sd": sd,
        "standard_error": se,
        **asdict(cfg),
    }
    results = {
        method: {
            **base,
            "method": method,
            "status": "ok",
            "ci_low": None,
            "ci_high": None,
            "invalid_pivot_fraction": None,
            "warnings": [],
            "assumptions": (
                "independent normal subject contrasts or adequate finite-variance CLT"
                if method == "t"
                else "independent representative finite-variance subjects; bootstrap approximation"
            ),
        }
        for method in methods
    }
    if n < 2 or se is None or not np.isfinite(se) or se == 0:
        status = (
            "insufficient_subjects"
            if n < 2
            else "degenerate_zero_variance"
            if se == 0
            else "nonfinite_standard_error"
        )
        for result in results.values():
            result["status"] = status
        return list(results.values())
    assert estimate is not None
    alpha = (1 - cfg.confidence) / 2
    if "t" in results:
        critical = float(stats.t.ppf(1 - alpha, n - 1))
        results["t"].update(ci_low=estimate - critical * se, ci_high=estimate + critical * se)
    shared = [method for method in methods if method in ("percentile", "basic", "studentized")]
    if shared:
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                boot = stats.bootstrap(
                    (x,),
                    _mean_se,
                    vectorized=True,
                    axis=-1,
                    method="percentile",
                    confidence_level=cfg.confidence,
                    n_resamples=cfg.n_resamples,
                    batch=256,
                    random_state=np.random.default_rng(cfg.seed),
                )
            distribution = np.asarray(boot.bootstrap_distribution)
            means, errors = distribution[0], distribution[1]
            lo, hi = np.quantile(means, [alpha, 1 - alpha])
            if "percentile" in results:
                results["percentile"].update(ci_low=float(lo), ci_high=float(hi))
            if "basic" in results:
                results["basic"].update(
                    ci_low=float(2 * estimate - hi), ci_high=float(2 * estimate - lo)
                )
            if "studentized" in results:
                valid = np.isfinite(errors) & (errors > 0) & np.isfinite(means)
                fraction = float(1 - valid.mean())
                result = results["studentized"]
                result["invalid_pivot_fraction"] = fraction
                if fraction > cfg.max_invalid_studentized_fraction or valid.sum() < 100:
                    result["status"] = "unreliable_studentized_standard_errors"
                else:
                    pivot = (means[valid] - estimate) / errors[valid]
                    low, high = np.quantile(pivot, [alpha, 1 - alpha])
                    result.update(
                        ci_low=float(estimate - high * se), ci_high=float(estimate - low * se)
                    )
                    if fraction:
                        result["warnings"].append(
                            "invalid zero/nonfinite resampled SE pivots explicitly omitted"
                        )
            for method in shared:
                results[method]["warnings"].extend(str(item.message) for item in caught)
        except (ValueError, FloatingPointError, RuntimeError) as exc:
            for method in shared:
                results[method].update(status="bootstrap_failure", warnings=[str(exc)])
    if "bca" in results:
        try:
            # A separate SciPy call uses the same draw seed, so comparisons share draws.
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                boot_bca = stats.bootstrap(
                    (x,),
                    np.mean,
                    vectorized=True,
                    method="BCa",
                    confidence_level=cfg.confidence,
                    n_resamples=cfg.n_resamples,
                    batch=256,
                    random_state=np.random.default_rng(cfg.seed),
                )
            low, high = boot_bca.confidence_interval
            results["bca"]["warnings"] = [str(item.message) for item in caught]
            if caught or not np.isfinite([low, high]).all() or low > high:
                results["bca"]["status"] = "invalid_bca_adjustment"
            else:
                results["bca"].update(ci_low=float(low), ci_high=float(high))
        except (ValueError, FloatingPointError, RuntimeError) as exc:
            results["bca"].update(status="bca_failure", warnings=[str(exc)])
    for result in results.values():
        if (
            result["status"] == "ok"
            and not np.isfinite([result["ci_low"], result["ci_high"]]).all()
        ):
            result.update(status="nonfinite_interval", ci_low=None, ci_high=None)
        if result["status"] != "ok":
            result.update(ci_low=None, ci_high=None)
    return list(results.values())


def robust_locations(values: NDArray[np.float64], trim: float = 0.2) -> dict[str, Any]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all() or not 0 <= trim < 0.5:
        raise ValueError("Robust locations require finite subjects and trim in [0,.5)")
    return {
        "n_subjects": len(x),
        "mean": float(np.mean(x)) if len(x) else None,
        "median": float(np.median(x)) if len(x) else None,
        "trimmed_mean": float(stats.trim_mean(x, trim)) if len(x) else None,
        "trim_fraction": trim,
        "target_note": "median and trimmed location differ from population mean under asymmetry",
    }
