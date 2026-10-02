from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class BrandSchema(BaseModel):
    id: UUID
    name: str
    relative_fit: float
    confidence: float

    class Config:
        from_attributes = True

class ProductVariantSchema(BaseModel):
    id: UUID
    product_id: UUID
    size_label: str
    color: Optional[str] = None
    fabric: Optional[str] = None
    stretch: float
    chest_ease: Optional[float] = None
    waist_ease: Optional[float] = None
    inseam: Optional[float] = None
    sleeve_length: Optional[float] = None
    shoulder_width: Optional[float] = None

    class Config:
        from_attributes = True

class ProductSchema(BaseModel):
    id: UUID
    brand_id: UUID
    brand: BrandSchema
    name: str
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    currency: str
    silhouette_type: str
    structure_level: str
    color_family: str
    visual_density: str
    fabric_drape: Optional[str] = None

    class Config:
        from_attributes = True

class ProductDetailsSchema(ProductSchema):
    variants: List[ProductVariantSchema]

    class Config:
        from_attributes = True
