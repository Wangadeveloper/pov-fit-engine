from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.fit_profile import FitProfile
from app.models.product import Product, ProductVariant

# ---------------------------------------------------------------------------
# Standard sizing scales used across all engines
# ---------------------------------------------------------------------------

TOPS_SCALE: List[str] = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
BOTTOMS_SCALE: List[str] = ["26", "28", "29", "30", "31", "32", "33", "34", "36", "38", "40"]

CATEGORY_KEYWORDS_BOTTOM = frozenset(
    ["jeans", "trousers", "shorts", "pants", "bottoms"]
)


def is_bottom_category(category: str) -> bool:
    cat = category.lower()
    return any(kw in cat for kw in CATEGORY_KEYWORDS_BOTTOM)


def get_scale(category: str) -> List[str]:
    return BOTTOMS_SCALE if is_bottom_category(category) else TOPS_SCALE


def get_size_index(size: str, scale: List[str]) -> int:
    try:
        return scale.index(size)
    except ValueError:
        return len(scale) // 2


def find_closest_available(recommended: str, available: List[str], scale: List[str]) -> str:
    rec_idx = get_size_index(recommended, scale)
    closest_size = available[0]
    min_distance = len(scale)
    for size in available:
        idx = get_size_index(size, scale)
        dist = abs(idx - rec_idx)
        if dist < min_distance:
            min_distance = dist
            closest_size = size
    return closest_size


# ---------------------------------------------------------------------------
# Bundled user context — passed between service and engines
# ---------------------------------------------------------------------------

@dataclass
class UserHistory:
    profile: FitProfile
    closet: List[ClosetItem] = field(default_factory=list)
    feedback: List[FitFeedback] = field(default_factory=list)


def normalize_inputs(
    user_profile: FitProfile | UserHistory | None = None,
    user_closet: List[ClosetItem] | None = None,
    user_feedback: List[FitFeedback] | None = None,
    product: Product | Dict[str, Any] | None = None,
    variants: List[ProductVariant] | None = None,
    brand: Brand | None = None,
    user_history: UserHistory | None = None,
):
    """Normalize signature parameters into consistent objects/lists."""
    if isinstance(user_profile, UserHistory):
        user_history = user_profile
        product = user_closet
        user_profile = None
        user_closet = None

    if user_history is not None:
        profile = user_history.profile
        closet = user_history.closet or []
        feedback = user_history.feedback or []
    else:
        profile = user_profile
        closet = user_closet or []
        feedback = user_feedback or []

    return profile, closet, feedback, product, variants or [], brand


# ---------------------------------------------------------------------------
# Abstract engine interface
# ---------------------------------------------------------------------------

class RecommendationEngine(ABC):
    """All recommendation engines implement this interface."""

    @abstractmethod
    def recommend(
        self,
        user_profile: FitProfile | None = None,
        user_closet: List[ClosetItem] | None = None,
        user_feedback: List[FitFeedback] | None = None,
        product: Product | Dict[str, Any] | None = None,
        variants: List[ProductVariant] | None = None,
        brand: Brand | None = None,
        user_history: UserHistory | None = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns a dict with at minimum:
            recommended_size: str
            fit_score: float          (0–100)
            confidence: float         (0–1)
            fit_prediction: dict
            reason: str
            explanation: list[str]

        ML engines may additionally include:
            fit_probability: float
            model_version: str
            recommendation_source: str  ("rule" | "ml" | "hybrid")
        """
        raise NotImplementedError
