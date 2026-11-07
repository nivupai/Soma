"""Validated pyRiemann affine-invariant operations; no test-reference updating."""

from typing import Any

import numpy as np
from pyriemann.classification import MDM
from pyriemann.geometry.distance import distance_riemann
from pyriemann.geometry.mean import mean_riemann
from pyriemann.tangentspace import TangentSpace
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from soma.decoding.covariance import require_spd
from soma.decoding.data import FloatArray


def riemannian_distance(A: FloatArray, B: FloatArray) -> float:
    require_spd(np.stack([A, B]))
    return float(distance_riemann(A, B))


def riemannian_mean(X: FloatArray) -> FloatArray:
    require_spd(X)
    return np.asarray(mean_riemann(X, tol=1e-10, maxiter=100))


class TrainingTangentSpace(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    def fit(self, X: FloatArray, y: Any = None) -> "TrainingTangentSpace":
        require_spd(X)
        self.space_ = TangentSpace(metric="riemann", tsupdate=False).fit(X)
        self.reference_ = self.space_.reference_.copy()
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "space_")
        require_spd(X)
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Tangent covariance dimensions changed")
        result = self.space_.transform(X)
        if not np.array_equal(self.space_.reference_, self.reference_):
            raise RuntimeError("Test data changed the training-only tangent reference")
        return np.asarray(result)


class CovarianceMDM(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    def __init__(self, metric: str = "riemann") -> None:
        self.metric = metric

    def fit(self, X: FloatArray, y: Any) -> "CovarianceMDM":
        require_spd(X)
        if self.metric not in ("euclid", "riemann") or set(np.unique(y)) != {0, 1}:
            raise ValueError("MDM requires both binary classes and an explicit metric")
        self.model_ = MDM(metric=self.metric, n_jobs=1).fit(X, y)
        self.classes_ = np.asarray(self.model_.classes_)
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X: FloatArray) -> Any:
        check_is_fitted(self, "model_")
        return self.model_.predict(require_spd(X))

    def decision_function(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "model_")
        distances = self.model_.transform(require_spd(X))
        return np.asarray(distances[:, 0] - distances[:, 1])
