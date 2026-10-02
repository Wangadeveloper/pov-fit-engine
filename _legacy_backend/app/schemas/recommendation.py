from pydantic import BaseModel
from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime

class RecommendationSchema(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    recommended_size: str
    fit_score: float
    confidence_score: float
    fit_prediction: Dict[str, str]
    explanation: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

class RecommendationResponse(BaseModel):
    recommended_size: str
    fit_score: float
    confidence: float
    fit_prediction: Dict[str, str]
    reason: str
    explanation: List[str]

class RecommendationEventCreate(BaseModel):
    recommendation_id: Optional[UUID] = None
    event_type: str
