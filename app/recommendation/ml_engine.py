"""
ML Recommendation Engine.

Uses a pre-trained LightGBM model to predict P(perfect_fit) for every
available candidate size, then selects the highest-probability size.

Falls back to a rule-engine-style explanation if the model is unavailable.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.fit_profile import FitProfile
from app.models.product import Product, ProductVariant
from app.recommendation.base import (
    RecommendationEngine,
    UserHistory,
    find_closest_available,
    get_scale,
    is_bottom_category,
    normalize_inputs,
)
from ml.feature_builder import build_feature_matrix
from ml.model_loader import load_meta, load_model
from ml.predictor import predict_sizes, top_prediction

logger = logging.getLogger(__name__)


class MLRecommendationEngine(RecommendationEngine):
    """
    LightGBM-based personalisation engine.

    Parameters
    ----------
    model_path : path to a trained LightGBM .txt model file
    model_version : version string stored in response metadata
    """

    RECOMMENDATION_SOURCE = "ml"

    def __init__(self, model_path: str = "models/pov_fit_model.txt", model_version: str = "unknown"):
        self.model_path = model_path
        self.model_version = model_version
        self._model = None      # lazy-loaded on first call
        self._meta: Optional[Dict] = None

    def _ensure_loaded(self) -> bool:
        """Load model if not yet loaded. Returns True if model is available."""
        if self._model is not None:
            return True
        self._model = load_model(self.model_path)
        self._meta = load_meta(self.model_path) if self._model else {}
        # Read version from metadata if not explicitly provided
        if self._meta and self.model_version == "unknown":
            self.model_version = self._meta.get("model_version", "unknown")
        return self._model is not None

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
            available_sizes = product.get("available_sizes", [])
        else:
            available_sizes = [v.size_label for v in variants] if variants else []

        if not available_sizes:
            return self._fallback_result("No product variants available.", available_sizes=[])

        if not self._ensure_loaded():
            return self._fallback_result("ML model unavailable.", available_sizes=available_sizes)

        # Build feature matrix (one row per candidate size)
        try:
            matrix, sizes = build_feature_matrix(
                user_profile=user_profile,
                user_closet=user_closet,
                user_feedback=user_feedback,
                product=product,
                candidate_sizes=available_sizes,
                brand=brand,
            )
        except Exception as exc:
            logger.error("Feature building failed: %s", exc)
            return self._fallback_result("Feature engineering error.", available_sizes=available_sizes)

        # Run inference
        predictions = predict_sizes(
            model=self._model,
            feature_matrix=matrix,
            candidate_sizes=sizes,
            meta=self._meta,
        )

        if not predictions:
            return self._fallback_result("Inference returned no results.", available_sizes=available_sizes)

        best = top_prediction(predictions)
        if not best or best.size not in available_sizes:
            # Safety: snap to closest available
            scale = get_scale(product.category)
            best_size = (
                find_closest_available(best.size, available_sizes, scale)
                if best
                else available_sizes[0]
            )
        else:
            best_size = best.size

        # Fit score: scaled from probability
        fit_probability = best.fit_probability if best else 0.5
        confidence = best.calibrated_confidence if best else 0.3
        fit_score = round(max(50.0, min(100.0, fit_probability * 100.0)), 1)

        # Regional fit prediction (body-attribute based)
        fit_prediction = self._build_fit_prediction(user_profile, product)

        # Explanation from top signals
        explanation = self._build_explanation(
            user_profile=user_profile,
            user_closet=user_closet,
            user_feedback=user_feedback,
            product=product,
            brand=brand,
            recommended_size=best_size,
            fit_probability=fit_probability,
        )

        reason = self._build_reason(
            user_closet=user_closet,
            product=product,
            brand=brand,
            recommended_size=best_size,
        )

        return {
            "recommended_size": best_size,
            "fit_score": fit_score,
            "confidence": round(confidence, 3),
            "fit_probability": round(fit_probability, 3),
            "fit_prediction": fit_prediction,
            "reason": reason,
            "explanation": explanation,
            "model_version": self.model_version,
            "recommendation_source": self.RECOMMENDATION_SOURCE,
            "all_predictions": [
                {"size": p.size, "probability": p.fit_probability}
                for p in predictions
            ],
        }

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _build_fit_prediction(self, user_profile: FitProfile, product: Any) -> Dict[str, str]:
        category = product.get("category", "tops") if isinstance(product, dict) else (product.category if product and hasattr(product, "category") else "tops")
        is_bot = is_bottom_category(category)
        cat_key = "bottoms" if is_bot else "tops"
        fit_prediction = {"shoulders": "good", "chest": "good", "length": "good"}
        attributes = getattr(user_profile, "attributes", []) or []
        for attr in attributes:
            if getattr(attr, "category", "").lower() == cat_key and getattr(attr, "attribute_key", "") in fit_prediction:
                val = getattr(attr, "attribute_value", "good")
                if val == "tight":
                    fit_prediction[attr.attribute_key] = "slightly_tight"
                elif val == "loose":
                    fit_prediction[attr.attribute_key] = "slightly_loose"
                else:
                    fit_prediction[attr.attribute_key] = val
        return fit_prediction

    def _build_explanation(
        self,
        user_profile: FitProfile,
        user_closet: List[ClosetItem],
        user_feedback: List[FitFeedback],
        product: Any,
        brand: Any,
        recommended_size: str,
        fit_probability: float,
    ) -> List[str]:
        explanation = []
        category = (product.get("category", "tops") if isinstance(product, dict) else (product.category if product and hasattr(product, "category") else "tops")).lower()
        is_bot = is_bottom_category(category)
        brand_name_lower = (product.get("brand", "") if isinstance(product, dict) else (brand.name if brand else "")).lower()

        # Closet signal
        def _get_c_cat(c):
            return (c.get("category") if isinstance(c, dict) else getattr(c, "category", "")).lower()
        def _get_c_brand(c):
            return (c.get("brand") if isinstance(c, dict) else getattr(c, "brand_name", "")).lower()

        cat_closet = [c for c in (user_closet or []) if _get_c_cat(c) == category]
        if cat_closet:
            explanation.append(
                f"Your purchase history in this category suggests {recommended_size} is your best fit."
            )

        # Brand history
        brand_closet = [c for c in (user_closet or []) if brand_name_lower and _get_c_brand(c) == brand_name_lower]
        if brand_closet:
            explanation.append("POV has verified sizes you already own from this brand.")

        # Return history
        brand_returns = [
            f for f in user_feedback
            if f.purchase and f.purchase.variant and brand
            and f.purchase.variant.product.brand_id == brand.id
            and f.outcome_label == "returned"
        ]
        if brand_returns:
            explanation.append(
                "Your previous feedback from this brand has been taken into account."
            )

        # Brand sizing bias
        if brand and abs(brand.relative_fit) >= 0.4:
            direction = "smaller" if brand.relative_fit < 0 else "larger"
            explanation.append(f"This brand tends to run {direction} than standard sizing.")

        # Probability signal
        if fit_probability >= 0.75:
            explanation.append(
                f"Our model is confident {recommended_size} will be a great fit for you."
            )
        elif fit_probability >= 0.55:
            explanation.append(
                f"Based on your history, {recommended_size} is our best estimate for this product."
            )
        else:
            explanation.append(
                "We have limited data to personalise this recommendation — consider checking size charts."
            )

        return explanation

    def _build_reason(
        self,
        user_closet: List[ClosetItem],
        product: Any,
        brand: Any,
        recommended_size: str,
    ) -> str:
        cat_name = product.get("category", "Tops") if isinstance(product, dict) else (product.category if product and hasattr(product, "category") else "Tops")
        category = cat_name.lower()
        brand_name = (product.get("brand", "") if isinstance(product, dict) else (brand.name if brand else ""))
        brand_name_lower = brand_name.lower()

        def _get_c_cat(c):
            return (c.get("category") if isinstance(c, dict) else getattr(c, "category", "")).lower()
        def _get_c_brand(c):
            return (c.get("brand") if isinstance(c, dict) else getattr(c, "brand_name", "")).lower()

        cat_closet = [c for c in (user_closet or []) if _get_c_cat(c) == category]
        if cat_closet:
            return f"Personalised based on your history in {cat_name}."
        if brand_name and any(_get_c_brand(c) == brand_name_lower for c in (user_closet or [])):
            return f"Personalised based on your sizing history with {brand_name}."
        return f"Estimated best fit for your profile: {recommended_size}."

    def _fallback_result(self, reason_msg: str, available_sizes: List[str]) -> Dict[str, Any]:
        size = available_sizes[0] if available_sizes else "M"
        return {
            "recommended_size": size,
            "fit_score": 50.0,
            "confidence": 0.25,
            "fit_probability": None,
            "fit_prediction": {"shoulders": "good", "chest": "good", "length": "good"},
            "reason": reason_msg,
            "explanation": [reason_msg],
            "model_version": self.model_version,
            "recommendation_source": self.RECOMMENDATION_SOURCE,
            "all_predictions": [],
        }
