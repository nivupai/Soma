"""Fresh sklearn pipelines and small prespecified grids; no external fitted models."""

from typing import Any

from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

from soma.decoding.config import MODELS
from soma.decoding.covariance import SymmetricVectorizer, TrialCovariances, ValidatedCovariances
from soma.decoding.csp import TrainingCSP
from soma.decoding.features import TrainingBursts
from soma.decoding.riemannian import CovarianceMDM, TrainingTangentSpace


def make_pipeline(
    model: str,
    protocol: dict[str, Any],
    params: dict[str, Any] | None = None,
    *,
    precomputed_covariance: bool = False,
) -> Pipeline:
    if model not in MODELS:
        raise ValueError("Unsupported decoder")
    fixed = protocol["fixed"]
    lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    logistic = LogisticRegression(
        C=fixed["logistic_C"], max_iter=1000, solver="lbfgs", random_state=protocol["seed"]
    )
    scale = StandardScaler()
    covariance = TrialCovariances(
        estimator=fixed["covariance_estimator"],
        relative_floor=fixed["covariance_relative_floor"],
        trace_normalize=fixed["covariance_trace_normalize"],
    )
    matrix_input: Any = ValidatedCovariances() if precomputed_covariance else covariance
    steps: list[tuple[str, Any]]
    if model in ("motor_mu_lr", "multiband_lr"):
        steps = [("scale", scale), ("classifier", logistic)]
    elif model == "motor_bands_lda":
        steps = [("scale", scale), ("classifier", lda)]
    elif model == "burst_lr":
        steps = [
            (
                "bursts",
                TrainingBursts(
                    protocol["fs_hz"],
                    fixed["burst_low_multiplier"],
                    fixed["burst_high_multiplier"],
                    fixed["burst_min_cycles"],
                ),
            ),
            ("scale", scale),
            ("classifier", logistic),
        ]
    elif model == "csp_lda":
        steps = [
            ("csp", TrainingCSP(fixed["csp_components"], fixed["csp_regularization"])),
            ("classifier", lda),
        ]
    elif model == "covariance_lda":
        steps = [
            ("covariance", matrix_input),
            ("vector", SymmetricVectorizer()),
            ("scale", scale),
            ("classifier", lda),
        ]
    elif model in ("euclidean_mdm", "riemann_mdm"):
        steps = [
            ("covariance", matrix_input),
            ("classifier", CovarianceMDM("euclid" if model == "euclidean_mdm" else "riemann")),
        ]
    else:
        steps = [
            ("covariance", matrix_input),
            ("tangent", TrainingTangentSpace()),
            ("scale", scale),
            ("classifier", logistic),
        ]
    pipeline = Pipeline(steps)
    if params:
        pipeline.set_params(**params)
    return pipeline


def parameter_grid(model: str, protocol: dict[str, Any], tune: bool) -> list[dict[str, Any]]:
    if not tune:
        return [{}]
    search = protocol["search"]
    if model == "csp_lda":
        return [
            {"csp__n_components": n, "csp__reg": reg}
            for n in search["csp_components"]
            for reg in search["csp_regularization"]
        ]
    if model.endswith("lr"):
        return [{"classifier__C": c} for c in search["logistic_C"]]
    return [{}]


def require_unfitted(pipeline: Pipeline) -> None:
    for _, step in pipeline.steps:
        try:
            check_is_fitted(step)
        except NotFittedError:
            continue
        raise ValueError("Prefitted transformation/classifier rejected before constructing folds")
