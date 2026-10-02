from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.core.database import get_db
from app.models.user import User
from app.models.fit_profile import FitProfile
from app.models.closet import ClosetItem
from app.models.purchase import Purchase
from app.models.feedback import FitFeedback
from app.models.recommendation import Recommendation, RecommendationEvent
from typing import Any, Dict

router = APIRouter()


@router.get("/dashboard", response_model=Dict[str, Any])
async def analytics_dashboard(db: AsyncSession = Depends(get_db)) -> Any:
    user_count = len((await db.execute(select(User))).scalars().all())
    profile_count = len((await db.execute(select(FitProfile))).scalars().all())
    closet_count = len((await db.execute(select(ClosetItem))).scalars().all())
    purchase_count = len((await db.execute(select(Purchase))).scalars().all())
    feedback_count = len((await db.execute(select(FitFeedback))).scalars().all())
    rec_count = len((await db.execute(select(Recommendation))).scalars().all())
    event_count = len((await db.execute(select(RecommendationEvent))).scalars().all())

    # Average confidence
    profiles = (await db.execute(select(FitProfile))).scalars().all()
    avg_confidence = sum(p.confidence for p in profiles) / len(profiles) if profiles else 0

    # Outcome breakdown
    kept = len((await db.execute(select(FitFeedback).where(FitFeedback.outcome_label == "kept"))).scalars().all())
    returned = len((await db.execute(select(FitFeedback).where(FitFeedback.outcome_label == "returned"))).scalars().all())

    return {
        "success": True,
        "data": {
            "users": user_count,
            "completed_fit_profiles": profile_count,
            "closet_items": closet_count,
            "purchases": purchase_count,
            "feedback_submissions": feedback_count,
            "recommendations_generated": rec_count,
            "recommendation_events": event_count,
            "average_confidence": round(avg_confidence, 2),
            "outcomes": {
                "kept": kept,
                "returned": returned,
            },
        },
        "error": None,
    }
