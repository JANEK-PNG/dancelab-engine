"""Prediction Error proxy (spec §6). STATUS: candidate — experimental, ADR-005.

PE(t) = d(E_obs(t), E_pred(t))

v0 proxies: unusual build-up length, delayed drop, sudden density change,
sudden bass change, unusual energy change.
"""

from __future__ import annotations

import numpy as np

from dancelab.core.errors import NotImplementedFeature

STATUS = "candidate"


def prediction_error_proxy(features_over_time: dict[str, np.ndarray]) -> np.ndarray:
    raise NotImplementedFeature("prediction error proxy", status=STATUS)
