from pydantic import BaseModel, Field
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime

class ClosetItemBase(BaseModel):
    brand_name: str
    category: str
    subcategory: Optional[str] = None
    size_label: str
    color: Optional[str] = None
    fit_label: Optional[str] = None
    fit_rating: str  # too_tight | a_little_tight | perfect | a_little_loose | too_loose
    tight_loose_regions: Dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None
    image_url: Optional[str] = None

class ClosetItemCreate(ClosetItemBase):
    pass

class ClosetItemUpdate(BaseModel):
    fit_rating: Optional[str] = None
    tight_loose_regions: Optional[Dict[str, str]] = None
    notes: Optional[str] = None

class ClosetItemSchema(ClosetItemBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
