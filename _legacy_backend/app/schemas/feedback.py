from pydantic import BaseModel, Field
from typing import Dict, Optional
from uuid import UUID
from datetime import datetime

class FitFeedbackCreate(BaseModel):
    purchase_id: UUID
    outcome_label: str  # kept | returned | exchanged
    reason_label: Optional[str] = None  # too_tight | too_loose | didnt_like_fit | didnt_like_style | fabric_discomfort | other
    tight_loose_regions: Dict[str, str] = Field(default_factory=dict)
    would_buy_again: bool = True
    final_size_worn: Optional[str] = None

class FitFeedbackSchema(BaseModel):
    id: UUID
    user_id: UUID
    purchase_id: UUID
    outcome_label: str
    reason_label: Optional[str] = None
    tight_loose_regions: Dict[str, str]
    would_buy_again: bool
    final_size_worn: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
