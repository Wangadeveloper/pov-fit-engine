from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.schemas.product import ProductVariantSchema

class PurchaseCreate(BaseModel):
    product_variant_id: UUID

class PurchaseSchema(BaseModel):
    id: UUID
    user_id: UUID
    product_variant_id: UUID
    purchase_date: datetime
    status: str
    variant: Optional[ProductVariantSchema] = None

    class Config:
        from_attributes = True
