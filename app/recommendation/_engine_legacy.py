from app.models.fit_profile import FitProfile
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.product import Product, ProductVariant
from app.models.brand import Brand
from typing import List, Dict, Any, Optional

# Standard sizing scales for navigation
TOPS_SCALE = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
BOTTOMS_SCALE = ["26", "28", "29", "30", "31", "32", "33", "34", "36", "38", "40"]

class RecommendationEngine:
    def recommend(
        self,
        user_profile: FitProfile,
        user_closet: List[ClosetItem],
        user_feedback: List[FitFeedback],
        product: Product,
        variants: List[ProductVariant],
        brand: Brand
    ) -> Dict[str, Any]:
        raise NotImplementedError


class RuleBasedRecommendationEngine(RecommendationEngine):
    def recommend(
        self,
        user_profile: FitProfile,
        user_closet: List[ClosetItem],
        user_feedback: List[FitFeedback],
        product: Product,
        variants: List[ProductVariant],
        brand: Brand
    ) -> Dict[str, Any]:
        # 1. Fallback if no variants exist
        if not variants:
            return {
                "recommended_size": "M",
                "fit_score": 50.0,
                "confidence": 0.25,
                "fit_prediction": {
                    "shoulders": "good",
                    "chest": "good",
                    "length": "good"
                },
                "reason": "Not enough inventory data available.",
                "explanation": ["No product sizing options found in current inventory."]
            }

        available_sizes = [v.size_label for v in variants]
        category = product.category.lower()
        is_bottom = any(kw in category for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
        
        # Determine base scale
        scale = BOTTOMS_SCALE if is_bottom else TOPS_SCALE
        default_size = "32" if is_bottom else "M"
        
        # 2. Extract baseline size from Closet
        matching_closet_items = [
            item for item in user_closet 
            if item.category.lower() == category
        ]
        
        size_counts: Dict[str, int] = {}
        for item in matching_closet_items:
            if item.fit_rating in ["perfect", "a_little_tight", "a_little_loose"]:
                size_counts[item.size_label] = size_counts.get(item.size_label, 0) + 1
        
        if size_counts:
            baseline_size = max(size_counts, key=size_counts.get)
        else:
            baseline_size = default_size

        # 3. Apply Brand sizing deviations
        shifted_index = self._get_size_index(baseline_size, scale)
        brand_shift = brand.relative_fit if brand else 0.0  # -1.0 runs small, +1.0 runs large
        
        if brand_shift <= -0.5:
            shifted_index += 1
        elif brand_shift >= 0.5:
            shifted_index -= 1

        shifted_index = max(0, min(len(scale) - 1, shifted_index))
        recommended_size = scale[shifted_index]

        # 4. Silhouette Match Adjustments
        explanation = []
        user_pref = user_profile.preferred_bottom_fit if is_bottom else user_profile.preferred_top_fit
        prod_sil = product.silhouette_type
        
        if prod_sil == "oversized" and user_pref in ["fitted", "regular", "straight"]:
            shifted_index_sil = self._get_size_index(recommended_size, scale) - 1
            shifted_index_sil = max(0, shifted_index_sil)
            recommended_size = scale[shifted_index_sil]
            explanation.append("This garment has an oversized silhouette, so we recommend sizing down to achieve your preferred fit.")
        elif prod_sil == "slim" and user_pref == "relaxed":
            shifted_index_sil = self._get_size_index(recommended_size, scale) + 1
            shifted_index_sil = min(len(scale) - 1, shifted_index_sil)
            recommended_size = scale[shifted_index_sil]
            explanation.append("This garment is slim-cut, so we suggest sizing up to match your preferred relaxed style.")
        else:
            explanation.append(f"Matches your preference for {user_pref} silhouettes.")

        # 5. Outcome/Feedback Adjustments
        brand_feedback = [
            fb for fb in user_feedback 
            if fb.purchase and fb.purchase.variant and brand and fb.purchase.variant.product.brand_id == brand.id
        ]
        
        for fb in brand_feedback:
            purchased_size = fb.purchase.variant.size_label
            if fb.outcome_label == "returned" and fb.reason_label == "too_tight" and purchased_size == recommended_size:
                shifted_idx = min(len(scale) - 1, self._get_size_index(recommended_size, scale) + 1)
                recommended_size = scale[shifted_idx]
                explanation.append("Adjusted to a larger size based on your previous return in this brand for being too tight.")
                break
            elif fb.outcome_label == "returned" and fb.reason_label == "too_loose" and purchased_size == recommended_size:
                shifted_idx = max(0, self._get_size_index(recommended_size, scale) - 1)
                recommended_size = scale[shifted_idx]
                explanation.append("Adjusted to a smaller size based on your previous return in this brand for being too loose.")
                break

        if recommended_size not in available_sizes:
            recommended_size = self._find_closest_available(recommended_size, available_sizes, scale)

        # 6. Confidence Score
        confidence = 0.25
        closet_count = len(matching_closet_items)
        confidence += min(0.30, closet_count * 0.10)
        
        has_brand_history = any(item.brand_name.lower() == (brand.name.lower() if brand else "") for item in user_closet)
        if has_brand_history:
            confidence += 0.15
            explanation.append("POV has verified sizes you already own from this brand.")
        else:
            brand_name = brand.name if brand else "this brand"
            explanation.append(f"We don't know {brand_name} very well yet, but we are basing recommendations on your closet profile.")

        feedback_count = len([
            fb for fb in user_feedback 
            if fb.purchase and fb.purchase.variant and fb.purchase.variant.product.category.lower() == category
        ])
        confidence += min(0.20, feedback_count * 0.10)
        confidence = min(0.95, confidence)
        
        fit_score = 90.0
        if confidence < 0.5:
            fit_score -= 10.0
        if prod_sil != user_pref:
            fit_score -= 5.0
        fit_score = max(50.0, min(100.0, fit_score))

        # 7. Fit prediction
        fit_prediction = {
            "shoulders": "good",
            "chest": "good",
            "length": "good"
        }
        
        profile_attributes = [attr for attr in user_profile.attributes if attr.category.lower() == category]
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
            explanation.append(f"Matches the size you wear most frequently in this category ({baseline_size}).")
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
            "explanation": explanation
        }

    def _get_size_index(self, size: str, scale: List[str]) -> int:
        try:
            return scale.index(size)
        except ValueError:
            return len(scale) // 2

    def _find_closest_available(self, recommended: str, available: List[str], scale: List[str]) -> str:
        rec_idx = self._get_size_index(recommended, scale)
        closest_size = available[0]
        min_distance = len(scale)
        
        for size in available:
            idx = self._get_size_index(size, scale)
            dist = abs(idx - rec_idx)
            if dist < min_distance:
                min_distance = dist
                closest_size = size
                
        return closest_size
