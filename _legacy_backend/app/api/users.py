from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.fit_profile import FitProfile
from app.models.closet import ClosetItem
from app.models.purchase import Purchase
from app.models.feedback import FitFeedback
from typing import Any, Dict
import json

router = APIRouter()


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(FitProfile).where(FitProfile.user_id == current_user.id).options(
        selectinload(FitProfile.attributes)
    )
    res = await db.execute(stmt)
    profile = res.scalars().first()

    return {
        "success": True,
        "data": {
            "id": str(current_user.id),
            "email": current_user.email,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "has_fit_profile": profile is not None,
            "onboarding_complete": profile is not None and profile.profile_completeness > 0.4,
        },
        "error": None,
    }


@router.delete("/me", response_model=Dict[str, Any])
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await db.delete(current_user)
    await db.commit()
    return {
        "success": True,
        "data": {"message": "Account and all associated data deleted."},
        "error": None,
    }


@router.get("/me/export", response_model=Dict[str, Any])
async def export_user_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    # Profile
    stmt_p = select(FitProfile).where(FitProfile.user_id == current_user.id).options(
        selectinload(FitProfile.attributes)
    )
    profile = (await db.execute(stmt_p)).scalars().first()

    # Closet
    closet = (await db.execute(select(ClosetItem).where(ClosetItem.user_id == current_user.id))).scalars().all()

    # Purchases
    purchases = (await db.execute(select(Purchase).where(Purchase.user_id == current_user.id))).scalars().all()

    # Feedback
    feedbacks = (await db.execute(select(FitFeedback).where(FitFeedback.user_id == current_user.id))).scalars().all()

    export = {
        "user": {"id": str(current_user.id), "email": current_user.email},
        "fit_profile": {
            "preferred_top_fit": profile.preferred_top_fit if profile else None,
            "preferred_bottom_fit": profile.preferred_bottom_fit if profile else None,
            "preferred_jacket_fit": profile.preferred_jacket_fit if profile else None,
            "comfort_preferences": profile.comfort_preferences if profile else [],
            "confidence": profile.confidence if profile else 0,
        } if profile else None,
        "closet_items": [
            {"brand": c.brand_name, "category": c.category, "size": c.size_label, "fit_rating": c.fit_rating}
            for c in closet
        ],
        "purchases": [
            {"id": str(p.id), "variant_id": str(p.product_variant_id), "status": p.status}
            for p in purchases
        ],
        "feedback": [
            {"purchase_id": str(f.purchase_id), "outcome": f.outcome_label, "would_buy_again": f.would_buy_again}
            for f in feedbacks
        ],
    }

    return {"success": True, "data": export, "error": None}
