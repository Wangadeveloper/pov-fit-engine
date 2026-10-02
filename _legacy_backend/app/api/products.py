from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.product import Product, ProductVariant
from app.models.brand import Brand
from app.schemas.product import ProductSchema, ProductDetailsSchema, BrandSchema
from typing import Any, Dict, Optional, List
import uuid

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
async def list_products(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> Any:
    stmt = select(Product).options(selectinload(Product.brand))

    if category:
        stmt = stmt.where(Product.category == category)
    if brand:
        stmt = stmt.join(Brand).where(Brand.name == brand)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))

    result = await db.execute(stmt)
    products = result.scalars().all()
    products_data = [ProductSchema.model_validate(p).model_dump() for p in products]
    return {"success": True, "data": products_data, "error": None}


@router.get("/brands", response_model=Dict[str, Any])
async def list_brands(db: AsyncSession = Depends(get_db)) -> Any:
    result = await db.execute(select(Brand))
    brands = result.scalars().all()
    brands_data = [BrandSchema.model_validate(b).model_dump() for b in brands]
    return {"success": True, "data": brands_data, "error": None}


@router.get("/categories", response_model=Dict[str, Any])
async def list_categories(db: AsyncSession = Depends(get_db)) -> Any:
    result = await db.execute(select(Product.category).distinct())
    categories = [row[0] for row in result.all()]
    return {"success": True, "data": categories, "error": None}


@router.get("/{product_id}", response_model=Dict[str, Any])
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(Product).where(Product.id == product_id).options(
        selectinload(Product.brand),
        selectinload(Product.variants),
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    if not product:
        return {
            "success": False,
            "data": None,
            "error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found."},
        }
    product_data = ProductDetailsSchema.model_validate(product).model_dump()
    return {"success": True, "data": product_data, "error": None}
