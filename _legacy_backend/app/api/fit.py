from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.fit_service import FitService
from app.schemas.fit import FitProfileSchema, FitProfileUpdate, OnboardingDetails
from typing import Any, Dict

router = APIRouter()


@router.get("/profile", response_model=Dict[str, Any])
async def get_fit_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    profile = await FitService.get_or_create_profile(db, current_user.id)
    profile_data = FitProfileSchema.model_validate(profile)
    return {"success": True, "data": profile_data.model_dump(), "error": None}


@router.patch("/profile", response_model=Dict[str, Any])
async def update_fit_profile(
    update_data: FitProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    profile = await FitService.update_profile(db, current_user.id, update_data)
    profile_data = FitProfileSchema.model_validate(profile)
    return {"success": True, "data": profile_data.model_dump(), "error": None}


@router.post("/onboarding", response_model=Dict[str, Any])
async def save_onboarding(
    data: OnboardingDetails,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    profile = await FitService.save_onboarding(db, current_user.id, data)
    profile_data = FitProfileSchema.model_validate(profile)
    return {"success": True, "data": profile_data.model_dump(), "error": None}


@router.get("/confidence", response_model=Dict[str, Any])
async def get_confidence(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    from sqlalchemy.future import select
    from app.models.closet import ClosetItem
    from app.models.feedback import FitFeedback

    profile = await FitService.get_or_create_profile(db, current_user.id)

    closet_count = len(
        (await db.execute(select(ClosetItem).where(ClosetItem.user_id == current_user.id))).scalars().all()
    )
    feedback_count = len(
        (await db.execute(select(FitFeedback).where(FitFeedback.user_id == current_user.id))).scalars().all()
    )

    return {
        "success": True,
        "data": {
            "confidence": profile.confidence,
            "calibration_level": profile.calibration_level,
            "profile_completeness": profile.profile_completeness,
            "signals": {
                "closet_items": closet_count,
                "feedback_submissions": feedback_count,
                "has_visual_preferences": bool(profile.preferred_top_fit),
                "has_comfort_preferences": bool(profile.comfort_preferences),
                "has_measurements": bool(profile.height_cm or profile.weight_kg),
            },
        },
        "error": None,
    }
