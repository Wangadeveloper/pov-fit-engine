"""
Recommendation module public API.

Import `get_engine()` to obtain the engine configured by the environment.

Usage::

    from app.recommendation import get_engine

    engine = get_engine()
    result = engine.recommend(...)
"""
from __future__ import annotations

import os

from app.recommendation.base import RecommendationEngine  # noqa: F401 — re-exported
from app.recommendation.rule_engine import RuleBasedRecommendationEngine
from app.recommendation.ml_engine import MLRecommendationEngine
from app.recommendation.hybrid_engine import HybridRecommendationEngine

# Keep the old import path alive for any external code that references engine.py
# via `from app.recommendation.engine import RuleBasedRecommendationEngine`
# (backwards compatibility shim).
try:
    import app.recommendation.engine as _legacy_engine  # noqa: F401
except ImportError:
    pass


def get_engine(
    engine_type: str | None = None,
    model_path: str | None = None,
    min_confidence: float | None = None,
) -> RecommendationEngine:
    """
    Factory function — returns the configured recommendation engine.

    Priority: explicit arguments > environment variables > defaults.

    Env vars
    --------
    RECOMMENDATION_ENGINE   : "hybrid" (default) | "ml" | "rule"
    ML_MODEL_PATH           : path to LightGBM .txt model file
    ML_MIN_CONFIDENCE       : float threshold for hybrid fallback
    """
    engine_type = (
        engine_type
        or os.environ.get("RECOMMENDATION_ENGINE", "hybrid")
    ).lower()

    model_path = model_path or os.environ.get("ML_MODEL_PATH", "models/pov_fit_model.txt")
    min_confidence = min_confidence or float(os.environ.get("ML_MIN_CONFIDENCE", "0.55"))

    if engine_type == "rule":
        return RuleBasedRecommendationEngine()

    if engine_type == "ml":
        return MLRecommendationEngine(model_path=model_path)

    # Default: hybrid
    ml = MLRecommendationEngine(model_path=model_path)
    rule = RuleBasedRecommendationEngine()
    return HybridRecommendationEngine(
        ml_engine=ml,
        rule_engine=rule,
        min_confidence=min_confidence,
    )


__all__ = [
    "RecommendationEngine",
    "RuleBasedRecommendationEngine",
    "MLRecommendationEngine",
    "HybridRecommendationEngine",
    "get_engine",
]
