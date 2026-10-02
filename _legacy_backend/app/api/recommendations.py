from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.recommendation import Recommendation, RecommendationEvent
from app.services.recommendation_service import RecommendationService
from app.schemas.recommendation import RecommendationEventCreate
from typing import Any, Dict, Optional, List
import uuid

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    category: Optional[str] = Query(None),
    limit: int = Query(20, le=50),
) -> Any:
    """Get personalized product recommendations for the current user."""
    stmt = select(Product).options(
        selectinload(Product.brand),
        selectinload(Product.variants),
    )
    if category:
        stmt = stmt.where(Product.category == category)

    result = await db.execute(stmt)
    products = list(result.scalars().all())[:limit]

    recs = await RecommendationService.get_recommendations_for_products_batch(
        db, current_user.id, products
    )

    # Sort by fit_score descending
    recs.sort(key=lambda x: x["fit_score"], reverse=True)

    return {"success": True, "data": recs, "error": None}


@router.get("/{product_id}", response_model=Dict[str, Any])
async def get_product_recommendation(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get size recommendation for a specific product."""
    try:
        rec_data = await RecommendationService.get_recommendation_for_product(
            db, current_user.id, product_id
        )
        return {"success": True, "data": rec_data, "error": None}
    except ValueError as e:
        return {
            "success": False,
            "data": None,
            "error": {"code": "PRODUCT_NOT_FOUND", "message": str(e)},
        }


@router.post("/events", response_model=Dict[str, Any])
async def log_recommendation_event(
    data: RecommendationEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    event = await RecommendationService.log_event(
        db, current_user.id, data.recommendation_id, data.event_type
    )
    return {
        "success": True,
        "data": {"id": str(event.id), "event_type": event.event_type},
        "error": None,
    }
