import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.fit_profile import FitProfile
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.product import Product, ProductVariant
from app.models.brand import Brand
from app.models.recommendation import Recommendation, RecommendationEvent
from app.recommendation import get_engine
from app.services.qloo_service import qloo_service


class RecommendationService:
    @staticmethod
    def get_user_context(db, user_id: uuid.UUID):
        # 1. Fetch User Profile
        stmt_profile = select(FitProfile).where(FitProfile.user_id == user_id).options(
            selectinload(FitProfile.attributes)
        )
        profile_res = db.session.execute(stmt_profile)
        profile = profile_res.scalars().first()
        if not profile:
            from app.services.fit_service import FitService
            profile = FitService.get_or_create_profile(db, user_id)

        # 2. Fetch User Closet
        stmt_closet = select(ClosetItem).where(ClosetItem.user_id == user_id)
        closet_res = db.session.execute(stmt_closet)
        closet = list(closet_res.scalars().all())

        # 3. Fetch User Feedback
        stmt_feedback = select(FitFeedback).where(FitFeedback.user_id == user_id).options(
            selectinload(FitFeedback.purchase)
        )
        feedback_res = db.session.execute(stmt_feedback)
        feedback = list(feedback_res.scalars().all())

        return profile, closet, feedback

    @staticmethod
    def _extract_cultural_profile(profile: FitProfile) -> Dict[str, Any]:
        return {
            "cultural_interests": getattr(profile, "cultural_interests", []) or [],
            "aesthetic_preference": getattr(profile, "aesthetic_preference", "casual") or "casual",
            "occasions": getattr(profile, "occasions", []) or [],
            "budget_tier": getattr(profile, "budget_tier", "accessible") or "accessible",
        }

    @staticmethod
    def get_recommendations_for_products_batch(
        db,
        user_id: uuid.UUID,
        products: List[Product],
        recommendation_mode: str = "qloo_enhanced"  # "qloo_enhanced" | "standard"
    ) -> List[Dict[str, Any]]:
        profile, closet, feedback = RecommendationService.get_user_context(db, user_id)
        user_cultural = RecommendationService._extract_cultural_profile(profile)
        engine = get_engine()

        recs = []
        db_recs = []

        for product in products:
            rec_data = engine.recommend(
                user_profile=profile,
                user_closet=closet,
                user_feedback=feedback,
                product=product,
                variants=product.variants or [],
                brand=product.brand
            )

            # Calculate Qloo cultural intelligence resonance
            cultural_res = qloo_service.calculate_cultural_resonance(product, user_cultural)
            cultural_score = cultural_res["resonance_score"]
            cultural_rationale = cultural_res["stylist_rationale"]

            if recommendation_mode == "qloo_enhanced":
                # Blended POV score: 50% physical fit + 50% cultural taste resonance
                composite_score = round((0.50 * rec_data["fit_score"]) + (0.50 * (cultural_score * 100.0)), 1)
                combined_explanation = [f"POV Stylist: {cultural_rationale}"] + rec_data["explanation"]
            else:
                # Standard recommendation (physical fit only)
                composite_score = rec_data["fit_score"]
                combined_explanation = rec_data["explanation"]

            rec_item = {
                "product_id": str(product.id),
                "product_name": product.name,
                "brand_name": product.brand.name if product.brand else "",
                "category": product.category,
                "price": product.price,
                "currency": product.currency,
                "image_url": product.image_url,
                "silhouette_type": product.silhouette_type,
                "recommended_size": rec_data["recommended_size"],
                "fit_score": composite_score,
                "physical_fit_score": rec_data["fit_score"],
                "confidence": rec_data["confidence"],
                "fit_prediction": rec_data["fit_prediction"],
                "reason": rec_data["reason"],
                "explanation": combined_explanation,
                "fit_probability": rec_data.get("fit_probability"),
                "model_version": rec_data.get("model_version"),
                "recommendation_source": rec_data.get("recommendation_source", "rule"),
                # Qloo Cultural Stylist attributes
                "cultural_score": cultural_score,
                "cultural_match_level": cultural_res["cultural_match_level"],
                "cultural_rationale": cultural_rationale,
                "matched_tags": cultural_res["matched_tags"],
                "editorial_headline": cultural_res["editorial_headline"],
                "recommendation_type": recommendation_mode,
                "is_qloo_sandbox": cultural_res["is_sandbox"],
            }
            recs.append(rec_item)

            db_recs.append(
                Recommendation(
                    user_id=user_id,
                    product_id=product.id,
                    recommended_size=rec_data["recommended_size"],
                    fit_score=composite_score,
                    confidence_score=rec_data["confidence"] * 100.0,
                    fit_prediction=rec_data["fit_prediction"],
                    explanation=combined_explanation,
                    cultural_score=cultural_score,
                    cultural_rationale=cultural_rationale,
                    recommendation_type=recommendation_mode,
                )
            )

        if db_recs:
            db.session.add_all(db_recs)
            db.session.commit()

        # Sort recommendations by composite score descending
        recs.sort(key=lambda x: x["fit_score"], reverse=True)
        return recs

    @staticmethod
    def get_recommendation_for_product(
        db, 
        user_id: uuid.UUID, 
        product_id: uuid.UUID,
        recommendation_mode: str = "qloo_enhanced"
    ) -> Dict[str, Any]:
        profile, closet, feedback = RecommendationService.get_user_context(db, user_id)
        user_cultural = RecommendationService._extract_cultural_profile(profile)

        # Fetch Product, Variants, Brand
        stmt_product = select(Product).where(Product.id == product_id).options(
            selectinload(Product.brand),
            selectinload(Product.variants)
        )
        product_res = db.session.execute(stmt_product)
        product = product_res.scalars().first()
        if not product:
            raise ValueError("Product not found.")

        brand = product.brand
        variants = product.variants

        # Run Recommendation Engine
        engine = get_engine()
        rec_data = engine.recommend(
            user_profile=profile,
            user_closet=closet,
            user_feedback=feedback,
            product=product,
            variants=variants,
            brand=brand
        )

        # Run Qloo Cultural Intelligence
        cultural_res = qloo_service.calculate_cultural_resonance(product, user_cultural)
        cultural_score = cultural_res["resonance_score"]
        cultural_rationale = cultural_res["stylist_rationale"]

        if recommendation_mode == "qloo_enhanced":
            composite_score = round((0.50 * rec_data["fit_score"]) + (0.50 * (cultural_score * 100.0)), 1)
            combined_explanation = [f"POV Stylist: {cultural_rationale}"] + rec_data["explanation"]
        else:
            composite_score = rec_data["fit_score"]
            combined_explanation = rec_data["explanation"]

        # Persist Recommendation in DB
        db_rec = Recommendation(
            user_id=user_id,
            product_id=product_id,
            recommended_size=rec_data["recommended_size"],
            fit_score=composite_score,
            confidence_score=rec_data["confidence"] * 100.0,
            fit_prediction=rec_data["fit_prediction"],
            explanation=combined_explanation,
            cultural_score=cultural_score,
            cultural_rationale=cultural_rationale,
            recommendation_type=recommendation_mode,
        )
        db.session.add(db_rec)
        db.session.commit()
        db.session.refresh(db_rec)

        return {
            "recommended_size": db_rec.recommended_size,
            "fit_score": db_rec.fit_score,
            "physical_fit_score": rec_data["fit_score"],
            "confidence": db_rec.confidence_score / 100.0,
            "fit_prediction": db_rec.fit_prediction,
            "reason": rec_data["reason"],
            "explanation": db_rec.explanation,
            "cultural_score": cultural_score,
            "cultural_match_level": cultural_res["cultural_match_level"],
            "cultural_rationale": cultural_rationale,
            "matched_tags": cultural_res["matched_tags"],
            "editorial_headline": cultural_res["editorial_headline"],
            "recommendation_type": recommendation_mode,
            "is_qloo_sandbox": cultural_res["is_sandbox"],
            "fit_probability": rec_data.get("fit_probability"),
            "model_version": rec_data.get("model_version"),
            "recommendation_source": rec_data.get("recommendation_source", "rule"),
        }

    @staticmethod
    def compare_recommendations(
        db,
        user_id: uuid.UUID,
        products: List[Product]
    ) -> Dict[str, Any]:
        """
        Generates and compares Standard (control) vs Qloo-Enhanced (experimental) recommendations
        for the given products, evaluating relevance, scoring distribution, and ranking shifts.
        """
        standard_recs = RecommendationService.get_recommendations_for_products_batch(
            db, user_id, products, recommendation_mode="standard"
        )
        qloo_recs = RecommendationService.get_recommendations_for_products_batch(
            db, user_id, products, recommendation_mode="qloo_enhanced"
        )

        # Calculate average scores
        avg_standard_score = (
            round(sum(r["fit_score"] for r in standard_recs) / len(standard_recs), 1)
            if standard_recs else 0.0
        )
        avg_qloo_score = (
            round(sum(r["fit_score"] for r in qloo_recs) / len(qloo_recs), 1)
            if qloo_recs else 0.0
        )
        avg_cultural_resonance = (
            round(sum(r.get("cultural_score", 0.0) for r in qloo_recs) / len(qloo_recs), 2)
            if qloo_recs else 0.0
        )

        return {
            "user_id": str(user_id),
            "product_count": len(products),
            "standard_recommendations": standard_recs,
            "qloo_recommendations": qloo_recs,
            "evaluation_metrics": {
                "avg_standard_score": avg_standard_score,
                "avg_qloo_score": avg_qloo_score,
                "score_delta": round(avg_qloo_score - avg_standard_score, 1),
                "avg_cultural_resonance": avg_cultural_resonance,
                "personalization_lift_pct": round(
                    ((avg_qloo_score - avg_standard_score) / max(avg_standard_score, 1.0)) * 100.0, 1
                ),
            }
        }

    @staticmethod
    def log_event(
        db, 
        user_id: uuid.UUID, 
        recommendation_id: Optional[uuid.UUID], 
        event_type: str,
        recommendation_type: str = "qloo_enhanced"
    ) -> RecommendationEvent:
        event = RecommendationEvent(
            user_id=user_id,
            recommendation_id=recommendation_id,
            event_type=event_type,
            recommendation_type=recommendation_type,
        )
        db.session.add(event)
        db.session.commit()
        db.session.refresh(event)
        return event
