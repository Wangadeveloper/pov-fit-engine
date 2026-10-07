"""
Pydantic schemas used by the ML feature builder and predictor.
These validate the structured inputs and outputs at the boundary between
the application domain objects and the ML pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UserSnapshot(BaseModel):
    """Flattened user profile features passed to the feature builder."""
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    preferred_top_fit: str = "regular"
    preferred_bottom_fit: str = "straight"
    # Aggregated body attribute hints (category → region → value)
    body_attributes: Dict[str, Dict[str, str]] = Field(default_factory=dict)


class ClosetSnapshot(BaseModel):
    """Aggregated closet features — not the raw list of closet items."""
    closet_item_count: int = 0
    category_closet_count: int = 0
    category_mode_size: Optional[str] = None
    category_size_entropy: float = 0.0
    same_brand_item_count: int = 0
    same_brand_mode_size: Optional[str] = None
    perfect_fit_count: int = 0
    slightly_tight_count: int = 0
    slightly_loose_count: int = 0


class FeedbackSnapshot(BaseModel):
    """Aggregated purchase/feedback features."""
    total_purchases: int = 0
    category_purchases: int = 0
    brand_purchases: int = 0
    successful_fit_count: int = 0
    return_count: int = 0
    exchange_count: int = 0
    too_tight_count: int = 0
    too_loose_count: int = 0
    brand_too_tight_count: int = 0
    brand_too_loose_count: int = 0
    category_too_tight_count: int = 0
    category_too_loose_count: int = 0
    brand_fit_success_rate: float = 0.0
    category_fit_success_rate: float = 0.0
    user_fit_success_rate: float = 0.0


class ProductSnapshot(BaseModel):
    """Product-level features."""
    category: str
    brand_name: str
    silhouette_type: str = "regular"
    brand_relative_fit: float = 0.0
    available_size_count: int = 1
    structure_level: str = "balanced"


class CandidateRow(BaseModel):
    """
    One feature row representing a (user, product, candidate_size) triple.
    This is what gets fed to LightGBM.predict_proba() per call.
    """
    # User
    height_cm: float = 170.0
    weight_kg: float = 70.0
    bmi: float = 24.2
    preferred_fit_enc: int = 2          # encoded preferred fit for category type
    # Closet
    closet_item_count: int = 0
    category_closet_count: int = 0
    category_mode_size_numeric: float = -1.0   # -1 = unknown
    category_size_entropy: float = 0.0
    same_brand_item_count: int = 0
    same_brand_mode_size_numeric: float = -1.0
    perfect_fit_count: int = 0
    slightly_tight_count: int = 0
    slightly_loose_count: int = 0
    # Feedback
    total_purchases: int = 0
    category_purchases: int = 0
    brand_purchases: int = 0
    successful_fit_count: int = 0
    return_count: int = 0
    too_tight_count: int = 0
    too_loose_count: int = 0
    brand_too_tight_count: int = 0
    brand_too_loose_count: int = 0
    brand_fit_success_rate: float = 0.0
    category_fit_success_rate: float = 0.0
    user_fit_success_rate: float = 0.0
    # Product
    category_enc: int = 0
    silhouette_enc: int = 0
    brand_relative_fit: float = 0.0
    available_size_count: int = 1
    structure_level_enc: int = 0
    # Candidate size
    candidate_size_numeric: float = 2.0
    candidate_size_position: float = 0.5       # 0=smallest, 1=largest in this product's range
    candidate_size_delta_from_user_mode: float = 0.0
    candidate_size_delta_from_brand_mode: float = 0.0

    def to_list(self) -> List[float]:
        """Return feature values as an ordered list matching FEATURE_COLUMNS."""
        return [float(v) for v in self.model_dump().values()]


# Ordered list of feature column names — must match CandidateRow.model_dump() key order
FEATURE_COLUMNS: List[str] = list(CandidateRow.model_fields.keys())


class SizePrediction(BaseModel):
    """ML prediction result for a single candidate size."""
    size: str
    fit_probability: float
    calibrated_confidence: float


class MLRecommendationResult(BaseModel):
    """Full ML engine output for one (user, product) pair."""
    recommended_size: str
    fit_probability: float
    confidence: float
    fit_score: float
    fit_prediction: Dict[str, str]
    reason: str
    explanation: List[str]
    model_version: str
    recommendation_source: str = "ml"
    all_predictions: List[Dict[str, Any]] = Field(default_factory=list)
