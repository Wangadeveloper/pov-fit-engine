from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.feedback import FitFeedback
from app.services.feedback_service import FeedbackService
from app.schemas.feedback import FitFeedbackCreate, FitFeedbackSchema
from typing import Any, Dict

router = APIRouter()


@router.post("", response_model=Dict[str, Any])
async def submit_feedback(
    data: FitFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    try:
        fb = await FeedbackService.submit_feedback(db, current_user.id, data)
        fb_data = FitFeedbackSchema.model_validate(fb).model_dump()
        return {"success": True, "data": fb_data, "error": None}
    except ValueError as e:
        return {
            "success": False,
            "data": None,
            "error": {"code": "FEEDBACK_ERROR", "message": str(e)},
        }


@router.get("", response_model=Dict[str, Any])
async def list_feedback(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(FitFeedback).where(FitFeedback.user_id == current_user.id)
    )
    feedbacks = result.scalars().all()
    fb_data = [FitFeedbackSchema.model_validate(f).model_dump() for f in feedbacks]
    return {"success": True, "data": fb_data, "error": None}
