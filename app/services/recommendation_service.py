import uuid

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.fit_profile import FitProfile
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.product import Product, ProductVariant
from app.models.brand import Brand
from app.models.recommendation import Recommendation, RecommendationEvent
from app.recommendation.engine import RuleBasedRecommendationEngine
from typing import Dict, Any, List, Optional

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
    def get_recommendations_for_products_batch(
        db,
        user_id: uuid.UUID,
        products: List[Product]
    ) -> List[Dict[str, Any]]:
        profile, closet, feedback = RecommendationService.get_user_context(db, user_id)
        engine = RuleBasedRecommendationEngine()

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
            recs.append({
                "product_id": str(product.id),
                "product_name": product.name,
                "brand_name": product.brand.name if product.brand else "",
                "category": product.category,
                "price": product.price,
                "currency": product.currency,
                "image_url": product.image_url,
                "silhouette_type": product.silhouette_type,
                "recommended_size": rec_data["recommended_size"],
                "fit_score": rec_data["fit_score"],
                "confidence": rec_data["confidence"],
                "fit_prediction": rec_data["fit_prediction"],
                "reason": rec_data["reason"],
                "explanation": rec_data["explanation"],
            })
            db_recs.append(
                Recommendation(
                    user_id=user_id,
                    product_id=product.id,
                    recommended_size=rec_data["recommended_size"],
                    fit_score=rec_data["fit_score"],
                    confidence_score=rec_data["confidence"] * 100.0,
                    fit_prediction=rec_data["fit_prediction"],
                    explanation=rec_data["explanation"]
                )
            )

        if db_recs:
            db.session.add_all(db_recs)
            db.session.commit()

        return recs

    @staticmethod
    def get_recommendation_for_product(
        db, 
        user_id: uuid.UUID, 
        product_id: uuid.UUID
    ) -> Dict[str, Any]:
        profile, closet, feedback = RecommendationService.get_user_context(db, user_id)

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
        engine = RuleBasedRecommendationEngine()
        rec_data = engine.recommend(
            user_profile=profile,
            user_closet=closet,
            user_feedback=feedback,
            product=product,
            variants=variants,
            brand=brand
        )

        # Persist Recommendation in DB
        db_rec = Recommendation(
            user_id=user_id,
            product_id=product_id,
            recommended_size=rec_data["recommended_size"],
            fit_score=rec_data["fit_score"],
            confidence_score=rec_data["confidence"] * 100.0,
            fit_prediction=rec_data["fit_prediction"],
            explanation=rec_data["explanation"]
        )
        db.session.add(db_rec)
        db.session.commit()
        db.session.refresh(db_rec)

        return {
            "recommended_size": db_rec.recommended_size,
            "fit_score": db_rec.fit_score,
            "confidence": db_rec.confidence_score / 100.0,
            "fit_prediction": db_rec.fit_prediction,
            "reason": rec_data["reason"],
            "explanation": db_rec.explanation
        }

    @staticmethod
    def log_event(
        db, 
        user_id: uuid.UUID, 
        recommendation_id: Optional[uuid.UUID], 
        event_type: str
    ) -> RecommendationEvent:
        event = RecommendationEvent(
            user_id=user_id,
            recommendation_id=recommendation_id,
            event_type=event_type
        )
        db.session.add(event)
        db.session.commit()
        db.session.refresh(event)
        return event
