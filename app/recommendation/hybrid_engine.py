"""
Hybrid Recommendation Engine.

Orchestrates ML and rule engines:

  1. Ask ML model for candidate-size probabilities.
  2. If confidence >= ML_MIN_CONFIDENCE → apply guardrails → return ML result.
  3. Otherwise → fall back to rule engine.
  4. Always guarantee: returned size is in available_sizes.
  5. Never let model errors break the API.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.fit_profile import FitProfile
from app.models.product import Product, ProductVariant
from app.recommendation.base import RecommendationEngine, UserHistory, normalize_inputs
from app.recommendation.ml_engine import MLRecommendationEngine
from app.recommendation.rule_engine import RuleBasedRecommendationEngine

logger = logging.getLogger(__name__)


class HybridRecommendationEngine(RecommendationEngine):
    """
    Production engine that uses ML as the primary signal and rules as fallback.

    Parameters
    ----------
    ml_engine      : MLRecommendationEngine instance
    rule_engine    : RuleBasedRecommendationEngine instance
    min_confidence : threshold below which ML result is discarded in favour of rules
    """

    RECOMMENDATION_SOURCE = "hybrid"

    def __init__(
        self,
        ml_engine: MLRecommendationEngine,
        rule_engine: RuleBasedRecommendationEngine,
        min_confidence: float = 0.55,
    ):
        self.ml_engine = ml_engine
        self.rule_engine = rule_engine
        self.min_confidence = min_confidence

    def recommend(
        self,
        user_profile: FitProfile | None = None,
        user_closet: List[ClosetItem] | None = None,
        user_feedback: List[FitFeedback] | None = None,
        product: Product | Dict[str, Any] | None = None,
        variants: List[ProductVariant] | None = None,
        brand: Brand | None = None,
        user_history: UserHistory | None = None,
        **kwargs,
    ) -> Dict[str, Any]:

        user_profile, user_closet, user_feedback, product, variants, brand = normalize_inputs(
            user_profile, user_closet, user_feedback, product, variants, brand, user_history
        )

        if isinstance(product, dict):
            available_sizes = set(product.get("available_sizes", []))
        else:
            available_sizes = {v.size_label for v in variants} if variants else set()

        # ── Try ML ──────────────────────────────────────────────────────────
        ml_result: Dict[str, Any] = {}
        try:
            ml_result = self.ml_engine.recommend(
                user_profile=user_profile,
                user_closet=user_closet,
                user_feedback=user_feedback,
                product=product,
                variants=variants,
                brand=brand,
            )
        except Exception as exc:
            logger.warning("ML engine raised an exception: %s — falling back to rules.", exc)

        ml_prob = ml_result.get("fit_probability")
        if ml_prob is None or not isinstance(ml_prob, (int, float)):
            ml_prob = ml_result.get("confidence", 0.0)
            if not isinstance(ml_prob, (int, float)):
                ml_prob = 1.0 if ml_prob == "High" else 0.5

        ml_ok = (
            bool(ml_result)
            and ml_result.get("recommendation_source") in ("ml", "hybrid")
            and ml_prob >= self.min_confidence
            and ml_result.get("recommended_size") in available_sizes
        )

        if ml_ok:
            result = ml_result
            result["recommendation_source"] = self.RECOMMENDATION_SOURCE
            logger.debug(
                "Hybrid: ML selected %s (conf=%.2f)",
                result["recommended_size"],
                result["confidence"],
            )
        else:
            # ── Fall back to rule engine ─────────────────────────────────────
            reason_parts = []
            if not ml_result:
                reason_parts.append("ML engine unavailable")
            elif ml_result.get("fit_probability") is None:
                reason_parts.append("ML model not loaded")
            elif ml_result.get("confidence", 0.0) < self.min_confidence:
                reason_parts.append(
                    f"ML confidence {ml_result.get('confidence', 0):.2f} < {self.min_confidence:.2f}"
                )
            elif ml_result.get("recommended_size") not in available_sizes:
                reason_parts.append("ML recommended unavailable size")

            logger.debug("Hybrid: rule fallback (%s)", "; ".join(reason_parts))

            result = self.rule_engine.recommend(
                user_profile=user_profile,
                user_closet=user_closet,
                user_feedback=user_feedback,
                product=product,
                variants=variants,
                brand=brand,
            )
            result["recommendation_source"] = "rule"
            # Attach ML metadata if available (so API consumers can inspect it)
            if ml_result.get("model_version"):
                result["model_version"] = ml_result["model_version"]
            if ml_result.get("fit_probability") is not None:
                result["fit_probability"] = ml_result["fit_probability"]

        # ── Final guardrail: size must be available ──────────────────────────
        if available_sizes and result.get("recommended_size") not in available_sizes:
            size_list = list(available_sizes)
            result["recommended_size"] = size_list[0]
            result.setdefault("explanation", []).append(
                "Size was adjusted to match current inventory availability."
            )

        return result
