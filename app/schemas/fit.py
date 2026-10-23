from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class FitAttributeSchema(BaseModel):
    category: str
    attribute_key: str
    attribute_value: str

    class Config:
        from_attributes = True

class FitProfileSchema(BaseModel):
    id: UUID
    user_id: UUID
    preferred_top_fit: str
    preferred_bottom_fit: str
    preferred_jacket_fit: str
    comfort_preferences: List[str]
    cultural_interests: List[str] = []
    aesthetic_preference: str = "casual"
    occasions: List[str] = []
    budget_tier: str = "accessible"
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    try_on_photo_url: Optional[str] = None
    confidence: float
    profile_completeness: float
    calibration_level: str
    attributes: List[FitAttributeSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FitProfileUpdate(BaseModel):
    preferred_top_fit: Optional[str] = None
    preferred_bottom_fit: Optional[str] = None
    preferred_jacket_fit: Optional[str] = None
    comfort_preferences: Optional[List[str]] = None
    cultural_interests: Optional[List[str]] = None
    aesthetic_preference: Optional[str] = None
    occasions: Optional[List[str]] = None
    budget_tier: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    try_on_photo_url: Optional[str] = None
    style_expression: Optional[str] = None

class OnboardingDetails(BaseModel):
    preferred_top_fit: str
    preferred_bottom_fit: str
    preferred_jacket_fit: str
    comfort_preferences: List[str] = []
    cultural_interests: List[str] = []
    aesthetic_preference: str = "casual"
    occasions: List[str] = []
    budget_tier: str = "accessible"
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    try_on_photo_url: Optional[str] = None
    style_expression: Optional[str] = None

