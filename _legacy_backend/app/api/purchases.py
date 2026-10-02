from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.purchase import Purchase
from app.models.product import ProductVariant
from app.schemas.purchase import PurchaseCreate, PurchaseSchema
from typing import Any, Dict
import uuid

router = APIRouter()


@router.post("", response_model=Dict[str, Any])
async def create_purchase(
    data: PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    # Verify variant exists
    stmt = select(ProductVariant).where(ProductVariant.id == data.product_variant_id)
    result = await db.execute(stmt)
    variant = result.scalars().first()
    if not variant:
        return {
            "success": False,
            "data": None,
            "error": {"code": "VARIANT_NOT_FOUND", "message": "Product variant not found."},
        }

    purchase = Purchase(
        user_id=current_user.id,
        product_variant_id=data.product_variant_id,
        status="purchased",
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)

    return {
        "success": True,
        "data": {
            "id": str(purchase.id),
            "product_variant_id": str(purchase.product_variant_id),
            "status": purchase.status,
            "purchase_date": purchase.purchase_date.isoformat() if purchase.purchase_date else None,
        },
        "error": None,
    }


@router.get("", response_model=Dict[str, Any])
async def list_purchases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Purchase)
        .where(Purchase.user_id == current_user.id)
        .options(selectinload(Purchase.variant))
    )
    result = await db.execute(stmt)
    purchases = result.scalars().all()
    purchases_data = []
    for p in purchases:
        purchases_data.append({
            "id": str(p.id),
            "product_variant_id": str(p.product_variant_id),
            "status": p.status,
            "purchase_date": p.purchase_date.isoformat() if p.purchase_date else None,
            "variant": {
                "size_label": p.variant.size_label if p.variant else None,
                "color": p.variant.color if p.variant else None,
                "fabric": p.variant.fabric if p.variant else None,
            } if p.variant else None,
        })
    return {"success": True, "data": purchases_data, "error": None}
