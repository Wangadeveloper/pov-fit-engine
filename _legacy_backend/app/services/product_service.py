import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.product import Product, ProductVariant
from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.fit_profile import FitProfile
from app.services.recommendation_service import RecommendationService
from typing import List, Dict, Any, Optional

# Supported colors, silhouettes, and categories for semantic parsing
COLORS = ["pink", "red", "blue", "green", "black", "white", "gray", "grey", "yellow", "orange", "purple", "brown", "navy", "cream", "beige"]
SILHOUETTES = ["slim", "regular", "relaxed", "oversized", "fitted", "straight", "loose"]
CATEGORIES = {
    "t-shirt": "T-Shirts", "t-shirts": "T-Shirts", "tee": "T-Shirts",
    "shirt": "Shirts", "shirts": "Shirts",
    "hoodie": "Hoodies", "hoodies": "Hoodies",
    "sweater": "Sweaters", "sweaters": "Sweaters",
    "jacket": "Jackets", "jackets": "Jackets", "coat": "Jackets",
    "jeans": "Jeans",
    "trouser": "Trousers", "trousers": "Trousers", "pants": "Trousers",
    "shorts": "Shorts",
    "dress": "Dresses", "dresses": "Dresses"
}

class ProductService:
    @staticmethod
    async def get_all_products(db: AsyncSession) -> List[Product]:
        stmt = select(Product).options(selectinload(Product.brand))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_product_by_id(db: AsyncSession, product_id: uuid.UUID) -> Optional[Product]:
        stmt = select(Product).where(Product.id == product_id).options(
            selectinload(Product.brand),
            selectinload(Product.variants)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def search_and_rank_products(
        db: AsyncSession, 
        user_id: uuid.UUID, 
        query: str,
        category_filter: Optional[str] = None,
        brand_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # 1. Fetch User Data for Personalized Ranking
        stmt_profile = select(FitProfile).where(FitProfile.user_id == user_id).options(
            selectinload(FitProfile.attributes)
        )
        profile_res = await db.execute(stmt_profile)
        user_profile = profile_res.scalars().first()
        
        stmt_closet = select(ClosetItem).where(ClosetItem.user_id == user_id)
        closet_res = await db.execute(stmt_closet)
        user_closet = closet_res.scalars().all()

        stmt_feedback = select(FitFeedback).where(FitFeedback.user_id == user_id)
        fb_res = await db.execute(stmt_feedback)
        user_feedback = fb_res.scalars().all()

        # 2. Parse Search Intent Semantically
        parsed_category = None
        parsed_color = None
        parsed_silhouette = None
        
        query_lower = query.lower()
        
        # Check category match
        for key, cat_val in CATEGORIES.items():
            if key in query_lower:
                parsed_category = cat_val
                break
                
        # Check color match
        for color in COLORS:
            if color in query_lower:
                parsed_color = color
                break
                
        # Check silhouette match
        for sil in SILHOUETTES:
            if sil in query_lower:
                parsed_silhouette = sil
                break

        # 3. Retrieve Products
        stmt_products = select(Product).options(
            selectinload(Product.brand),
            selectinload(Product.variants)
        )
        prod_res = await db.execute(stmt_products)
        all_prods = prod_res.scalars().all()

        # Rule-based engine for in-memory fit scoring during search ranking
        from app.recommendation.engine import RuleBasedRecommendationEngine
        rec_engine = RuleBasedRecommendationEngine()

        ranked_results = []
        
        for prod in all_prods:
            # Apply hard filters first (Category / Brand filters from UI dropdowns)
            if category_filter and prod.category.lower() != category_filter.lower():
                continue
            if brand_filter and prod.brand.name.lower() != brand_filter.lower():
                continue

            # Base relevance score
            relevance_score = 100.0
            
            # Match parsed query terms
            if parsed_category:
                if prod.category.lower() == parsed_category.lower():
                    relevance_score += 50.0
                else:
                    relevance_score -= 30.0  # discount other categories
            else:
                # General query text match
                if query_lower and (query_lower in prod.name.lower() or query_lower in prod.description.lower()):
                    relevance_score += 20.0
                    
            if parsed_color:
                if parsed_color == prod.color_family.lower() or parsed_color in prod.name.lower() or parsed_color in prod.description.lower():
                    relevance_score += 30.0
                    
            if parsed_silhouette:
                if parsed_silhouette == prod.silhouette_type.lower():
                    relevance_score += 30.0

            # 4. PERSONALIZATION BOOSTS
            
            # A. Fit Compatibility Boost
            try:
                rec = rec_engine.recommend(
                    user_profile=user_profile,
                    user_closet=user_closet,
                    user_feedback=user_feedback,
                    product=prod,
                    variants=prod.variants or [],
                    brand=prod.brand
                )
                fit_compatibility = rec["fit_score"]  # 0 to 100
                rec_size = rec["recommended_size"]
                confidence = rec["confidence"]
                fit_prediction = rec["fit_prediction"]
                explanation = rec["explanation"]
                reason = rec["reason"]
            except Exception:
                fit_compatibility = 70.0
                rec_size = "M"
                confidence = 0.5
                fit_prediction = {}
                explanation = ["Awaiting profile data to calibrate fit."]
                reason = "Based on standard profile defaults."

            # Boost score based on fit compatibility: up to +20% for excellent fit
            relevance_score += (fit_compatibility - 70.0) * 0.5

            # B. Aesthetic Alignment Boost
            if user_profile:
                category_lower = prod.category.lower()
                is_bottom = any(kw in category_lower for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
                pref_fit = user_profile.preferred_bottom_fit if is_bottom else user_profile.preferred_top_fit
                
                if prod.silhouette_type == pref_fit:
                    relevance_score += 15.0  # Matches user style preferences
                
                # Match structure preferences
                if "structured" in user_profile.comfort_preferences and prod.structure_level == "structured":
                    relevance_score += 10.0
                elif "soft" in user_profile.comfort_preferences and prod.structure_level == "soft":
                    relevance_score += 10.0

            # C. Past Purchase Outcomes Boost / Penalty
            for fb in user_feedback:
                if fb.purchase and fb.purchase.variant and fb.purchase.variant.product.brand_id == prod.brand_id:
                    if fb.outcome_label == "kept":
                        relevance_score += 10.0  # Trust this brand
                    elif fb.outcome_label == "returned":
                        relevance_score -= 15.0  # Penalty for past returns

            ranked_results.append({
                "product": prod,
                "relevance_score": round(relevance_score, 1),
                "personal_fit": {
                    "recommended_size": rec_size,
                    "fit_score": fit_compatibility,
                    "confidence": confidence,
                    "fit_prediction": fit_prediction,
                    "explanation": explanation,
                    "reason": reason
                }
            })

        # Sort by relevance_score descending
        ranked_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return ranked_results
