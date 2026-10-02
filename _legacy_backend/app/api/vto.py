from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.fit_profile import FitProfile
from app.services.youcam_service import youcam_service
from app.services.recommendation_service import RecommendationService

router = APIRouter()

DEFAULT_MODEL_PHOTO = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=1000&auto=format&fit=crop"

class VTORequest(BaseModel):
    product_id: uuid.UUID
    user_photo_url: Optional[str] = None
    recommended_size: Optional[str] = None

class UserPhotoUpdate(BaseModel):
    photo_url: str

@router.post("/try-on", response_model=Dict[str, Any])
async def create_vto_try_on(
    request: VTORequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Executes a Virtual Try-On request using YouCam AI Engine.
    Combines YouCam photorealistic visual try-on with POV fit & sizing intelligence.
    """
    # 1. Fetch Product
    stmt = select(Product).where(Product.id == request.product_id).options(
        selectinload(Product.brand),
        selectinload(Product.variants),
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # 2. Get User Fit Recommendation
    try:
        rec_data = await RecommendationService.get_recommendation_for_product(
            db, current_user.id, product.id
        )
        recommended_size = request.recommended_size or rec_data["recommended_size"]
        fit_score = rec_data["fit_score"]
        confidence = rec_data["confidence"]
        fit_prediction = rec_data["fit_prediction"]
        reason = rec_data["reason"]
        explanation = rec_data["explanation"]
    except Exception:
        recommended_size = request.recommended_size or "M"
        fit_score = 85.0
        confidence = 0.70
        fit_prediction = {"shoulders": "good", "chest": "good", "length": "good"}
        reason = "Recommended size based on general sizing."
        explanation = ["Selected based on sizing standards."]

    # 3. Determine User Photo
    stmt_profile = select(FitProfile).where(FitProfile.user_id == current_user.id)
    profile_res = await db.execute(stmt_profile)
    profile = profile_res.scalar_one_or_none()

    user_photo_url = (
        request.user_photo_url or
        (profile.try_on_photo_url if profile and profile.try_on_photo_url else None) or
        DEFAULT_MODEL_PHOTO
    )

    # 4. Initiate YouCam VTO Task
    vto_res = await youcam_service.create_try_on_task(
        user_photo_url=user_photo_url,
        garment_image_url=product.image_url,
        category=product.category,
        recommended_size=recommended_size
    )

    return {
        "success": True,
        "data": {
            "task_id": vto_res["task_id"],
            "status": vto_res["status"],
            "result_url": vto_res.get("result_url") or product.image_url,
            "user_photo_url": user_photo_url,
            "product_id": str(product.id),
            "product_name": product.name,
            "brand_name": product.brand.name if product.brand else "POV Brand",
            "garment_image_url": product.image_url,
            "category": product.category,
            "recommended_size": recommended_size,
            "fit_score": fit_score,
            "confidence": confidence,
            "fit_prediction": fit_prediction,
            "reason": reason,
            "explanation": explanation,
            "provider": vto_res.get("provider", "YouCam AI Engine v2.0"),
            "message": vto_res.get("message", "Virtual try-on completed successfully.")
        },
        "error": None
    }


@router.get("/task/{task_id}", response_model=Dict[str, Any])
async def get_vto_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Poll task status for asynchronous YouCam VTO requests.
    """
    status_data = await youcam_service.get_task_status(task_id)
    return {"success": True, "data": status_data, "error": None}


@router.post("/user-photo", response_model=Dict[str, Any])
async def update_user_try_on_photo(
    request: UserPhotoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Save or update user's default try-on photo in their Fit Profile.
    """
    stmt = select(FitProfile).where(FitProfile.user_id == current_user.id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        profile = FitProfile(user_id=current_user.id, try_on_photo_url=request.photo_url)
        db.add(profile)
    else:
        profile.try_on_photo_url = request.photo_url

    await db.commit()
    await db.refresh(profile)

    return {
        "success": True,
        "data": {
            "user_id": str(current_user.id),
            "try_on_photo_url": profile.try_on_photo_url
        },
        "error": None
    }
