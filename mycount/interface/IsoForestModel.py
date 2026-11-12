"""Fit scikit-learn independently of collection, Basic Bots, and HTTP requests."""

import pickle

import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

from mycount.constants.DIsoForest import DIsoForest
from mycount.entity.IsoForestObservation import IsoForestObservation
from mycount.entity.IsoForestResult import IsoForestResult


class IsoForestModel:
    def fit(self, observations: tuple[IsoForestObservation, ...]) -> IsoForestResult:
        model = IsolationForest(random_state=DIsoForest.RANDOM_SEED)
        manifest = {
            "feature_version": DIsoForest.FEATURE_VERSION,
            "features": DIsoForest.FEATURES, "parameters": model.get_params(),
            "sklearn_version": sklearn.__version__, "numpy_version": np.__version__,
            "ipv4_prefix": DIsoForest.IPV4_PREFIX, "ipv6_prefix": DIsoForest.IPV6_PREFIX,
            "window_hours": DIsoForest.WINDOW_HOURS,
        }
        if not observations:
            return IsoForestResult((), (), None, manifest)
        matrix = np.asarray([observation.features for observation in observations], dtype=np.float32)
        model.fit(matrix)
        decisions = tuple(float(value) for value in model.decision_function(matrix))
        return IsoForestResult(observations, decisions, pickle.dumps(model), manifest)
