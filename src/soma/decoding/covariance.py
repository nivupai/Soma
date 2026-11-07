"""Trial-local covariance estimation with measured rank and explicit SPD flooring."""

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.covariance import OAS, LedoitWolf
from sklearn.utils.validation import check_is_fitted

from soma.decoding.data import FloatArray, validate_tensor


def diagnostics(matrices: FloatArray) -> list[dict[str, float]]:
    if np.iscomplexobj(matrices):
        raise ValueError("Real symmetric covariances required")
    values = np.asarray(matrices, dtype=float)
    if (
        values.ndim != 3
        or values.shape[0] == 0
        or values.shape[1] == 0
        or values.shape[1] != values.shape[2]
        or not np.isfinite(values).all()
        or not np.all(
            np.linalg.norm(values - values.transpose(0, 2, 1), axis=(1, 2))
            <= 1e-10 * np.maximum(np.linalg.norm(values, axis=(1, 2)), np.finfo(float).tiny)
        )
    ):
        raise ValueError("Finite symmetric trial covariance matrices required")
    eigen = np.linalg.eigvalsh(values)
    return [
        {
            "minimum_eigenvalue": float(e[0]),
            "maximum_eigenvalue": float(e[-1]),
            "condition_number": float(e[-1] / e[0]) if e[0] > 0 else float("inf"),
            "numerical_rank": float(np.sum(e > max(0.0, e[-1]) * 1e-10)),
        }
        for e in eigen
    ]


def require_spd(matrices: FloatArray) -> FloatArray:
    rows = diagnostics(matrices)
    if any(row["minimum_eigenvalue"] <= 0 for row in rows):
        raise ValueError("Covariance is singular/indefinite; explicit regularization is required")
    return np.asarray(matrices, dtype=float)


class TrialCovariances(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Per-trial estimators; no train/test population statistics are pooled."""

    def __init__(
        self,
        estimator: str = "oas",
        shrinkage: float = 0.1,
        relative_floor: float = 1e-6,
        trace_normalize: bool = False,
    ) -> None:
        self.estimator = estimator
        self.shrinkage = shrinkage
        self.relative_floor = relative_floor
        self.trace_normalize = trace_normalize

    def fit(self, X: FloatArray, y: Any = None) -> "TrialCovariances":
        data = validate_tensor(X)
        if (
            self.estimator not in ("empirical", "shrinkage", "oas", "ledoit_wolf")
            or not 0 <= self.shrinkage <= 1
            or not np.isfinite(self.relative_floor)
            or self.relative_floor < 0
        ):
            raise ValueError("Invalid covariance estimator, shrinkage or eigenvalue floor")
        self.n_features_in_ = data.shape[1]
        return self

    def transform(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "n_features_in_")
        data = validate_tensor(X)
        if data.shape[1] != self.n_features_in_:
            raise ValueError("Covariance channel dimension changed")
        result, rows = [], []
        for trial in data:
            # Fixed V -> µV conversion; no learned scale or population covariance.
            samples = trial.T * 1e6
            centered = samples - samples.mean(axis=0)
            if self.estimator in ("oas", "ledoit_wolf"):
                estimator = OAS() if self.estimator == "oas" else LedoitWolf()
                covariance = np.asarray(estimator.fit(samples).covariance_)
            else:
                covariance = centered.T @ centered / len(centered)
                if self.estimator == "shrinkage":
                    target = np.trace(covariance) / len(covariance) * np.eye(len(covariance))
                    covariance = (1 - self.shrinkage) * covariance + self.shrinkage * target
            covariance = (covariance + covariance.T) / 2
            eigen, vectors = np.linalg.eigh(covariance)
            scale = float(np.trace(covariance) / len(covariance))
            if not np.isfinite(scale) or scale <= 0:
                raise ValueError("Zero-energy covariance cannot be made meaningfully SPD")
            before = float(eigen[0])
            if self.relative_floor:
                covariance = (vectors * np.maximum(eigen, self.relative_floor * scale)) @ vectors.T
                covariance = (covariance + covariance.T) / 2
            if self.trace_normalize:
                covariance /= np.trace(covariance)
            info = diagnostics(covariance[None])[0]
            info.update(
                minimum_before_floor=before,
                floor_scale=scale,
                rank_before_floor=float(np.sum(eigen > eigen[-1] * 1e-10)),
            )
            rows.append(info)
            result.append(covariance)
        self.last_diagnostics_ = rows
        return np.asarray(result)


class SymmetricVectorizer(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Frobenius-isometric upper triangle, an explicit Euclidean representation."""

    def fit(self, X: FloatArray, y: Any = None) -> "SymmetricVectorizer":
        require_spd(X)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "n_features_in_")
        require_spd(X)
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Covariance dimensions changed")
        i, j = np.triu_indices(X.shape[1])
        return np.asarray(X[:, i, j] * np.where(i == j, 1.0, np.sqrt(2)))


class ValidatedCovariances(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Validate already computed trial-local covariance, with no learned statistics."""

    def fit(self, X: FloatArray, y: Any = None) -> "ValidatedCovariances":
        require_spd(X)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "n_features_in_")
        require_spd(X)
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Cached covariance channel dimension changed")
        self.last_diagnostics_ = diagnostics(X)
        return np.asarray(X)
