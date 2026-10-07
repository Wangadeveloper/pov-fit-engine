"""
Predictor — wraps the loaded LightGBM booster for inference.

Handles:
  - Predicting P(perfect_fit) for all candidate sizes
  - Platt scaling calibration (loaded from model metadata)
  - Ranking sizes by probability
  - Graceful failure when the model is unavailable
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ml.schemas import SizePrediction

logger = logging.getLogger(__name__)


def _platt_scale(prob: float, a: float, b: float) -> float:
    """Sigmoid calibration: P_cal = 1 / (1 + exp(a * logit(p) + b))."""
    # Clamp to avoid log(0)
    prob = max(1e-7, min(1 - 1e-7, prob))
    logit = np.log(prob / (1 - prob))
    cal = 1.0 / (1.0 + np.exp(a * logit + b))
    return float(np.clip(cal, 0.0, 1.0))


def predict_sizes(
    model: Any,
    feature_matrix: List[List[float]],
    candidate_sizes: List[str],
    meta: Optional[Dict] = None,
) -> List[SizePrediction]:
    """
    Run inference for all candidate sizes and return ranked predictions.

    Parameters
    ----------
    model          : loaded LightGBM Booster
    feature_matrix : list of feature lists (one per candidate size)
    candidate_sizes: size labels in the same order as feature_matrix
    meta           : model metadata dict (may contain Platt calibration params)

    Returns
    -------
    List of SizePrediction sorted by fit_probability descending.
    """
    if model is None or not feature_matrix:
        return []

    try:
        import numpy as np  # noqa: PLC0415
        X = np.array(feature_matrix, dtype=np.float32)
        raw_probs = model.predict(X)          # shape: (n_candidates,) or (n, 2)

        # LGBMClassifier booster.predict() returns class-1 probability directly
        if raw_probs.ndim == 2:
            raw_probs = raw_probs[:, 1]

        # Platt calibration params from metadata
        platt_a = 1.0
        platt_b = 0.0
        if meta and "calibration" in meta:
            platt_a = meta["calibration"].get("a", 1.0)
            platt_b = meta["calibration"].get("b", 0.0)

        predictions = []
        for size, raw_p in zip(candidate_sizes, raw_probs):
            cal_p = _platt_scale(float(raw_p), platt_a, platt_b)
            predictions.append(
                SizePrediction(
                    size=size,
                    fit_probability=round(float(raw_p), 4),
                    calibrated_confidence=round(cal_p, 4),
                )
            )

        predictions.sort(key=lambda x: x.fit_probability, reverse=True)
        return predictions

    except Exception as exc:
        logger.error("Prediction error: %s", exc)
        return []


def top_prediction(predictions: List[SizePrediction]) -> Optional[SizePrediction]:
    """Return the highest-probability prediction, or None."""
    return predictions[0] if predictions else None
