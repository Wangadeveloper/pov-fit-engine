from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.closet_service import ClosetService
from app.schemas.closet import ClosetItemCreate, ClosetItemUpdate, ClosetItemSchema
from typing import Any, Dict, List
import uuid

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
async def list_closet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    items = await ClosetService.get_user_closet(db, current_user.id)
    items_data = [ClosetItemSchema.model_validate(i).model_dump() for i in items]
    return {"success": True, "data": items_data, "error": None}


@router.post("", response_model=Dict[str, Any])
async def add_closet_item(
    data: ClosetItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    item = await ClosetService.add_item(db, current_user.id, data)
    item_data = ClosetItemSchema.model_validate(item).model_dump()
    return {"success": True, "data": item_data, "error": None}


@router.patch("/{item_id}", response_model=Dict[str, Any])
async def update_closet_item(
    item_id: uuid.UUID,
    data: ClosetItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    item = await ClosetService.update_item(db, current_user.id, item_id, data)
    if not item:
        return {
            "success": False,
            "data": None,
            "error": {"code": "ITEM_NOT_FOUND", "message": "Closet item not found."},
        }
    item_data = ClosetItemSchema.model_validate(item).model_dump()
    return {"success": True, "data": item_data, "error": None}


@router.delete("/{item_id}", response_model=Dict[str, Any])
async def delete_closet_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    deleted = await ClosetService.delete_item(db, current_user.id, item_id)
    if not deleted:
        return {
            "success": False,
            "data": None,
            "error": {"code": "ITEM_NOT_FOUND", "message": "Closet item not found."},
        }
    return {"success": True, "data": {"message": "Item deleted."}, "error": None}
