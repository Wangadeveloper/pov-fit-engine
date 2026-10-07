from __future__ import annotations

from typing import Any, Dict, List

from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.fit_profile import FitProfile
from app.models.product import Product, ProductVariant
from app.recommendation.base import (
    BOTTOMS_SCALE,
    TOPS_SCALE,
    RecommendationEngine,
    UserHistory,
    find_closest_available,
    get_scale,
    get_size_index,
    is_bottom_category,
    normalize_inputs,
)


class RuleBasedRecommendationEngine(RecommendationEngine):
    """
    Deterministic rule-based size recommendation engine.

    Pipeline (7 steps):
        1. Fallback guard — no inventory → return generic M/32 at low confidence
        2. Closet baseline — most-owned size in the same category
        3. Brand bias correction — shift by brand.relative_fit
        4. Silhouette match — adjust for oversized/slim vs. user preference
        5. Return feedback loop — correct based on past too-tight/too-loose returns
        6. Confidence & fit score calculation
        7. Regional fit prediction from stored FitAttributes
    """

    RECOMMENDATION_SOURCE = "rule"

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

        # Handle dict product representation if passed directly
        if isinstance(product, dict):
            available_sizes = product.get("available_sizes", [])
            category = product.get("category", "Tops").lower()
            silhouette = product.get("silhouette", "regular").lower()
            brand_name = product.get("brand", "")
            brand_rel_fit = product.get("brand_relative_fit", 0.0)
        else:
            available_sizes = [v.size_label for v in variants] if variants else []
            category = (product.category if product and hasattr(product, "category") else "tops").lower()
            silhouette = (product.silhouette if product and hasattr(product, "silhouette") else "regular").lower()
            brand_name = brand.name if brand else ""
            brand_rel_fit = brand.relative_fit if brand else 0.0

        # ── Step 1: Fallback ────────────────────────────────────────────────
        if not available_sizes:
            return {
                "recommended_size": "M",
                "fit_score": 50.0,
                "confidence": 0.25,
                "fit_prediction": {"shoulders": "good", "chest": "good", "length": "good"},
                "reason": "Not enough inventory data available.",
                "explanation": ["No product sizing options found in current inventory."],
                "recommendation_source": self.RECOMMENDATION_SOURCE,
            }
        is_bottom = is_bottom_category(category)
        scale = BOTTOMS_SCALE if is_bottom else TOPS_SCALE
        default_size = "32" if is_bottom else "M"

        # ── Step 2: Baseline size from closet ───────────────────────────────
        matching_closet_items = [
            item for item in user_closet
            if item.category.lower() == category
        ]
        size_counts: Dict[str, int] = {}
        for item in matching_closet_items:
            if item.fit_rating in ["perfect", "a_little_tight", "a_little_loose"]:
                size_counts[item.size_label] = size_counts.get(item.size_label, 0) + 1

        baseline_size = max(size_counts, key=size_counts.get) if size_counts else default_size

        # ── Step 3: Brand sizing bias ────────────────────────────────────────
        shifted_index = get_size_index(baseline_size, scale)
        brand_shift = brand_rel_fit
        if brand_shift <= -0.5:
            shifted_index += 1
        elif brand_shift >= 0.5:
            shifted_index -= 1
        shifted_index = max(0, min(len(scale) - 1, shifted_index))
        recommended_size = scale[shifted_index]

        # ── Step 4: Silhouette preference ───────────────────────────────────
        explanation: List[str] = []
        user_pref = (
            getattr(user_profile, "preferred_bottom_fit", "straight")
            if is_bottom
            else getattr(user_profile, "preferred_top_fit", "regular")
        )
        prod_sil = silhouette

        if prod_sil == "oversized" and user_pref in ["fitted", "regular", "straight"]:
            idx_sil = max(0, get_size_index(recommended_size, scale) - 1)
            recommended_size = scale[idx_sil]
            explanation.append(
                "This garment has an oversized silhouette, so we recommend sizing down "
                "to achieve your preferred fit."
            )
        elif prod_sil == "slim" and user_pref == "relaxed":
            idx_sil = min(len(scale) - 1, get_size_index(recommended_size, scale) + 1)
            recommended_size = scale[idx_sil]
            explanation.append(
                "This garment is slim-cut, so we suggest sizing up to match your preferred "
                "relaxed style."
            )
        else:
            explanation.append(f"Matches your preference for {user_pref} silhouettes.")

        # ── Step 5: Return feedback loop ─────────────────────────────────────
        brand_feedback = [
            fb for fb in user_feedback
            if (
                isinstance(fb, dict) and fb.get("brand", "").lower() == brand_name.lower()
            ) or (
                hasattr(fb, "purchase") and fb.purchase and fb.purchase.variant and brand
                and fb.purchase.variant.product.brand_id == brand.id
            )
        ]
        for fb in brand_feedback:
            if isinstance(fb, dict):
                purchased_size = fb.get("size", fb.get("size_label", ""))
                outcome = fb.get("outcome", fb.get("outcome_label", ""))
                reason = fb.get("reason", fb.get("reason_label", fb.get("outcome", "")))
            else:
                purchased_size = fb.purchase.variant.size_label if fb.purchase and fb.purchase.variant else ""
                outcome = getattr(fb, "outcome_label", "")
                reason = getattr(fb, "reason_label", "")

            if (
                (outcome == "returned" and reason == "too_tight") or reason == "too_tight" or outcome == "too_tight"
            ) and purchased_size == recommended_size:
                idx = min(len(scale) - 1, get_size_index(recommended_size, scale) + 1)
                recommended_size = scale[idx]
                explanation.append(
                    "Adjusted to a larger size based on your previous return in this brand "
                    "for being too tight."
                )
                break
            elif (
                (outcome == "returned" and reason == "too_loose") or reason == "too_loose" or outcome == "too_loose"
            ) and purchased_size == recommended_size:
                idx = max(0, get_size_index(recommended_size, scale) - 1)
                recommended_size = scale[idx]
                explanation.append(
                    "Adjusted to a smaller size based on your previous return in this brand "
                    "for being too loose."
                )
                break

        # Snap to nearest available size
        if recommended_size not in available_sizes:
            recommended_size = find_closest_available(recommended_size, available_sizes, scale)

        # ── Step 6: Confidence & fit score ──────────────────────────────────
        confidence = 0.25
        closet_count = len(matching_closet_items)
        confidence += min(0.30, closet_count * 0.10)

        def _get_c_brand(c):
            return (c.get("brand") if isinstance(c, dict) else getattr(c, "brand_name", "")).lower()

        has_brand_history = any(
            _get_c_brand(item) == brand_name.lower()
            for item in user_closet
        )
        if has_brand_history:
            confidence += 0.15
            explanation.append("POV has verified sizes you already own from this brand.")
        else:
            b_name = brand_name if brand_name else "this brand"
            explanation.append(
                f"We don't know {b_name} very well yet, but we are basing "
                "recommendations on your closet profile."
            )

        def _get_fb_cat(fb):
            if isinstance(fb, dict):
                return fb.get("category", "").lower()
            if hasattr(fb, "purchase") and fb.purchase and fb.purchase.variant and fb.purchase.variant.product:
                return fb.purchase.variant.product.category.lower()
            return ""

        feedback_count = len([fb for fb in user_feedback if _get_fb_cat(fb) == category])
        confidence += min(0.20, feedback_count * 0.10)
        confidence = min(0.95, confidence)

        fit_score = 90.0
        if confidence < 0.5:
            fit_score -= 10.0
        if prod_sil != user_pref:
            fit_score -= 5.0
        fit_score = max(50.0, min(100.0, fit_score))

        # ── Step 7: Regional fit prediction ─────────────────────────────────
        fit_prediction: Dict[str, str] = {
            "shoulders": "good",
            "chest": "good",
            "length": "good",
        }
        cat_key = "bottoms" if is_bottom else "tops"
        profile_attributes = [
            attr
            for attr in user_profile.attributes
            if attr.category.lower() == cat_key
        ]
        for attr in profile_attributes:
            region = attr.attribute_key
            val = attr.attribute_value
            if region in fit_prediction:
                if val == "tight":
                    fit_prediction[region] = "slightly_tight"
                elif val == "loose":
                    fit_prediction[region] = "slightly_loose"
                else:
                    fit_prediction[region] = val

        if baseline_size in size_counts:
            explanation.append(
                f"Matches the size you wear most frequently in this category ({baseline_size})."
            )
        else:
            explanation.append("Selected based on your visual fit profile.")

        reason = f"You usually wear {baseline_size} in similar {category}."
        if brand and brand_shift <= -0.5:
            reason = f"Recommended size shifted up because {brand.name} runs small."
        elif brand and brand_shift >= 0.5:
            reason = f"Recommended size shifted down because {brand.name} runs large."

        return {
            "recommended_size": recommended_size,
            "fit_score": round(fit_score, 1),
            "confidence": round(confidence, 2),
            "fit_prediction": fit_prediction,
            "reason": reason,
            "explanation": explanation,
            "recommendation_source": self.RECOMMENDATION_SOURCE,
        }
