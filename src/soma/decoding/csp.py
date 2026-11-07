"""MNE CSP inside training pipelines; filters are sensor-space, not neural sources."""

from typing import Any

import mne
import numpy as np
from mne.decoding import CSP
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from soma.decoding.data import FloatArray, validate_tensor


class TrainingCSP(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    def __init__(
        self, n_components: int = 4, reg: float = 0.1, component_order: str = "mutual_info"
    ) -> None:
        self.n_components = n_components
        self.reg = reg
        self.component_order = component_order

    def fit(self, X: FloatArray, y: Any) -> "TrainingCSP":
        data = validate_tensor(X)
        if (
            not 1 <= self.n_components <= data.shape[1]
            or not 0 <= self.reg <= 1
            or self.component_order not in ("mutual_info", "alternate")
            or set(np.unique(y)) != {0, 1}
        ):
            raise ValueError("Invalid CSP dimensions, regularization, order or binary labels")
        self.n_features_in_ = data.shape[1]
        self.training_rank_ = int(np.linalg.matrix_rank(np.concatenate(data, axis=1)))
        if self.n_components > self.training_rank_:
            raise ValueError("CSP components exceed measured training channel rank")
        self.csp_ = CSP(
            n_components=self.n_components,
            reg=self.reg,
            log=True,
            cov_est="concat",
            norm_trace=False,
            rank=None,
            component_order=self.component_order,
        )
        with mne.use_log_level("ERROR"):
            self.csp_.fit(data * 1e6, y)
        self.filters_ = np.asarray(self.csp_.filters_).copy()
        self.patterns_ = np.asarray(self.csp_.patterns_).copy()
        return self

    def transform(self, X: FloatArray) -> FloatArray:
        check_is_fitted(self, "csp_")
        data = validate_tensor(X)
        if data.shape[1] != self.n_features_in_:
            raise ValueError("CSP channel dimension changed")
        with mne.use_log_level("ERROR"):
            result = self.csp_.transform(data * 1e6)
        if result.shape != (len(data), self.n_components) or not np.isfinite(result).all():
            raise ValueError("Invalid CSP log-variance features")
        return np.asarray(result)
