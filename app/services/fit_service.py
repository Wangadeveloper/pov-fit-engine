import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.fit_profile import FitProfile, FitAttribute
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.schemas.fit import FitProfileUpdate, OnboardingDetails

logger = logging.getLogger(__name__)


class FitService:
    @staticmethod
    def get_or_create_profile(db, user_id: uuid.UUID) -> FitProfile:
        stmt = select(FitProfile).where(FitProfile.user_id == user_id).options(
            selectinload(FitProfile.attributes)
        )
        result = db.session.execute(stmt)
        profile = result.scalars().first()
        
        if not profile:
            profile = FitProfile(
                user_id=user_id,
                preferred_top_fit="regular",
                preferred_bottom_fit="straight",
                preferred_jacket_fit="regular",
                comfort_preferences=[],
                cultural_interests=[],
                aesthetic_preference="casual",
                occasions=[],
                budget_tier="accessible",
                confidence=0.25,
                profile_completeness=0.15,
                calibration_level="low"
            )
            db.session.add(profile)
            db.session.commit()
            db.session.refresh(profile)
            
            # Reload to include attributes relationship
            stmt = select(FitProfile).where(FitProfile.id == profile.id).options(
                selectinload(FitProfile.attributes)
            )
            result = db.session.execute(stmt)
            profile = result.scalars().first()
            
        return profile

    @staticmethod
    def update_profile(db, user_id: uuid.UUID, update_data: FitProfileUpdate) -> FitProfile:
        profile = FitService.get_or_create_profile(db, user_id)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(profile, key, val)
            
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        db.session.refresh(profile)
        return profile

    @staticmethod
    def save_onboarding(db, user_id: uuid.UUID, data: OnboardingDetails) -> FitProfile:
        profile = FitService.get_or_create_profile(db, user_id)
        
        profile.preferred_top_fit = data.preferred_top_fit
        profile.preferred_bottom_fit = data.preferred_bottom_fit
        profile.preferred_jacket_fit = data.preferred_jacket_fit
        profile.comfort_preferences = data.comfort_preferences
        profile.cultural_interests = data.cultural_interests
        profile.aesthetic_preference = data.aesthetic_preference
        profile.occasions = data.occasions
        profile.budget_tier = data.budget_tier
        profile.height_cm = data.height_cm
        profile.weight_kg = data.weight_kg
        if data.style_expression is not None:
            profile.style_expression = data.style_expression
        
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        db.session.refresh(profile)
        return profile

    @staticmethod
    def add_or_update_attribute(
        db, 
        profile_id: uuid.UUID, 
        category: str, 
        key: str, 
        value: str
    ) -> FitAttribute:
        stmt = select(FitAttribute).where(
            FitAttribute.fit_profile_id == profile_id,
            FitAttribute.category == category,
            FitAttribute.attribute_key == key
        )
        result = db.session.execute(stmt)
        attribute = result.scalars().first()
        
        if attribute:
            attribute.attribute_value = value
        else:
            attribute = FitAttribute(
                fit_profile_id=profile_id,
                category=category,
                attribute_key=key,
                attribute_value=value
            )
            db.session.add(attribute)
            
        db.session.commit()
        return attribute

    @staticmethod
    def recalculate_metrics(db, profile: FitProfile) -> None:
        """Recalculate completeness, calibration level, and ML-backed confidence."""
        # 1. Recalculate Completeness
        completeness = 0.0
        
        # Base visual fits: 15% each (total 45%)
        if profile.preferred_top_fit: completeness += 0.15
        if profile.preferred_bottom_fit: completeness += 0.15
        if profile.preferred_jacket_fit: completeness += 0.15
        
        # Comfort preferences: 15%
        if profile.comfort_preferences: completeness += 0.15
        
        # Optional parameters (height/weight): 10%
        if profile.height_cm or profile.weight_kg: completeness += 0.10
        
        # Query closet items count
        stmt_closet = select(ClosetItem).where(ClosetItem.user_id == profile.user_id)
        res_closet = db.session.execute(stmt_closet)
        closet_items = res_closet.scalars().all()
        closet_count = len(closet_items)
        if closet_count > 0:
            completeness += 0.15  # 15% if they have at least 1 closet item
            
        # Query feedback count
        stmt_fb = select(FitFeedback).where(FitFeedback.user_id == profile.user_id)
        res_fb = db.session.execute(stmt_fb)
        feedbacks = res_fb.scalars().all()
        fb_count = len(feedbacks)
        if fb_count > 0:
            completeness += 0.15  # 15% if they have submitted feedback
            
        profile.profile_completeness = round(min(1.0, completeness), 2)
        
        # 2. Recalculate Calibration Level
        total_signals = closet_count + fb_count
        if total_signals >= 8:
            profile.calibration_level = "high"
        elif total_signals >= 3:
            profile.calibration_level = "medium"
        else:
            profile.calibration_level = "low"

        # 3. Recalculate Confidence Score — ML-first, rule-based fallback
        ml_confidence = FitService._get_ml_confidence(db, profile, closet_items, feedbacks)
        if ml_confidence is not None:
            profile.confidence = round(ml_confidence, 2)
        else:
            # Rule-based fallback
            confidence = 0.25
            confidence += min(0.30, closet_count * 0.10)
            confidence += min(0.40, fb_count * 0.15)
            profile.confidence = round(min(1.0, confidence), 2)

    @staticmethod
    def _get_ml_confidence(
        db,
        profile: FitProfile,
        closet_items: list,
        feedbacks: list,
    ) -> Optional[float]:
        """
        Query the ML engine against a probe product and return the Platt-calibrated
        confidence for this user's current profile state.

        Returns None if the model is unavailable or no products exist in the shop.
        """
        try:
            from app.recommendation import get_engine
            from app.models.product import Product
            from sqlalchemy.orm import selectinload as silo

            # Fetch a probe product (cheapest query — just the first available product)
            stmt = (
                select(Product)
                .options(silo(Product.brand), silo(Product.variants))
                .limit(1)
            )
            probe_product = db.session.execute(stmt).scalars().first()
            if not probe_product or not probe_product.variants:
                return None

            engine = get_engine()
            rec = engine.recommend(
                user_profile=profile,
                user_closet=list(closet_items),
                user_feedback=list(feedbacks),
                product=probe_product,
                variants=probe_product.variants,
                brand=probe_product.brand,
            )

            # Use fit_probability (raw ML output) whenever the model actually ran.
            # The hybrid engine may still fall back to rules for the *size recommendation*,
            # but it always attaches fit_probability from the ML model if it loaded.
            fit_prob = rec.get("fit_probability")
            model_ver = rec.get("model_version")

            if fit_prob is not None and model_ver:
                # ML model ran — use its raw probability as the profile confidence signal.
                # Scale: perfect-fit prob (1.0) → 0.95, low prob (0.3) → 0.30
                ml_confidence = round(min(0.95, max(0.25, float(fit_prob))), 2)
                source = rec.get("recommendation_source", "rule")
                logger.debug(
                    "ML confidence for user %s = %.2f (source=%s, fit_prob=%.3f, model=%s)",
                    profile.user_id, ml_confidence, source, fit_prob, model_ver,
                )
                return ml_confidence

            return None

        except Exception as exc:
            logger.warning("ML confidence probe failed: %s — using rule-based fallback", exc)
            return None

    @staticmethod
    def get_profile_completeness_details(
        profile: FitProfile,
        closet_count: int,
        fb_count: int,
    ) -> Dict[str, Any]:
        """
        Return a structured breakdown of profile completeness for the dashboard.

        Each item has:
          - label: human-readable name
          - done: bool
          - weight: % contribution to overall completeness
          - unlock: what completing this unlocks
          - action_url_name: Flask route name to redirect to (or None)
        """
        has_body_measurements = bool(profile.height_cm or profile.weight_kg)
        has_fit_preferences = bool(
            profile.preferred_top_fit
            and profile.preferred_bottom_fit
            and profile.preferred_jacket_fit
        )
        has_comfort_prefs = bool(profile.comfort_preferences)
        has_closet_items = closet_count > 0
        has_feedback = fb_count > 0
        has_photo = bool(profile.try_on_photo_url)

        items = [
            {
                "key": "fit_preferences",
                "label": "Fit Preferences",
                "description": "Tell us how you like tops, bottoms & jackets to fit",
                "done": has_fit_preferences,
                "weight": 45,
                "unlock": "Enables basic size recommendations",
                "action_url_name": "fit.onboarding",
                "icon": "👗",
            },
            {
                "key": "comfort_prefs",
                "label": "Comfort Style",
                "description": "Choose your comfort priorities (e.g. breathable, stretchy)",
                "done": has_comfort_prefs,
                "weight": 15,
                "unlock": "Improves silhouette matching accuracy",
                "action_url_name": "fit.onboarding",
                "icon": "🧘",
            },
            {
                "key": "measurements",
                "label": "Body Measurements",
                "description": "Add your height and/or weight",
                "done": has_body_measurements,
                "weight": 10,
                "unlock": "Unlocks size-chart cross-referencing in the ML model",
                "action_url_name": "fit.onboarding",
                "icon": "📏",
            },
            {
                "key": "closet_items",
                "label": "Wardrobe History",
                "description": "Log at least one item you already own",
                "done": has_closet_items,
                "weight": 15,
                "unlock": "Boosts ML confidence by up to +30%",
                "action_url_name": "closet.index",
                "icon": "🧺",
            },
            {
                "key": "feedback",
                "label": "Fit Feedback",
                "description": "Rate how past purchases actually fit",
                "done": has_feedback,
                "weight": 15,
                "unlock": "Personalises the ML model specifically to your body",
                "action_url_name": "shop.index",
                "icon": "⭐",
            },
            {
                "key": "photo",
                "label": "Try-On Photo",
                "description": "Upload a full-body photo for Virtual Try-On",
                "done": has_photo,
                "weight": 0,  # Bonus — doesn't count toward completeness %
                "unlock": "Enables Virtual Try-On feature",
                "action_url_name": "profile.index",
                "icon": "📸",
            },
        ]

        missing = [i for i in items if not i["done"]]
        done_count = sum(1 for i in items if i["done"])

        # Determine confidence source label.
        # The ML model runs if it's loaded (model file exists). Calibration level
        # reflects how well the model knows this user's preferences.
        source = "rule-based estimate"
        if profile.calibration_level == "high":
            source = "ML-powered · high calibration"
        elif profile.calibration_level == "medium":
            source = "ML-powered · medium calibration"
        elif has_closet_items or has_feedback:
            source = "ML-powered · low calibration"
        elif has_fit_preferences:
            source = "ML-powered · initial estimate"
        else:
            source = "rule-based estimate"

        return {
            "items": items,
            "missing": missing,
            "done_count": done_count,
            "total_count": len(items),
            "is_complete": profile.profile_completeness >= 0.85,
            "needs_attention": profile.profile_completeness < 0.5,
            "confidence_source": source,
            "profile_completeness_pct": int(profile.profile_completeness * 100),
            "confidence_pct": int(profile.confidence * 100),
        }
