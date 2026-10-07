"""
Feature builder — the single source of truth for feature engineering.

This module is used by BOTH:
  - ml/train.py    (offline training)
  - app/recommendation/ml_engine.py  (online inference)

Any change here applies to both, preventing train/serve skew.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.models.fit_profile import FitProfile
from app.models.product import Product, ProductVariant
from ml.schemas import CandidateRow, FEATURE_COLUMNS

# ---------------------------------------------------------------------------
# Encoding dictionaries  (stable — must not change between training runs)
# ---------------------------------------------------------------------------

TOPS_SCALE = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
BOTTOMS_SCALE = ["26", "28", "29", "30", "31", "32", "33", "34", "36", "38", "40"]

CATEGORY_ENC: Dict[str, int] = {
    "t-shirts": 0, "shirts": 1, "hoodies": 2, "sweaters": 3,
    "jackets": 4, "jeans": 5, "trousers": 6, "shorts": 7,
    "dresses": 8, "tops": 0, "bottoms": 5, "other": 9,
}

SILHOUETTE_ENC: Dict[str, int] = {
    "slim": 0, "regular": 1, "straight": 2,
    "relaxed": 3, "oversized": 4, "other": 5,
}

TOP_FIT_ENC: Dict[str, int] = {"fitted": 0, "regular": 1, "relaxed": 2, "oversized": 3}
BOTTOM_FIT_ENC: Dict[str, int] = {"slim": 0, "straight": 1, "relaxed": 2, "wide": 3}
STRUCTURE_ENC: Dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def _is_bottom(category: str) -> bool:
    cat = category.lower()
    return any(k in cat for k in ["jeans", "trousers", "shorts", "pants", "bottoms"])


def _get_scale(category: str) -> List[str]:
    return BOTTOMS_SCALE if _is_bottom(category) else TOPS_SCALE


def _size_to_numeric(size: str, scale: List[str]) -> float:
    try:
        return float(scale.index(size))
    except ValueError:
        return float(len(scale) // 2)


def _mode_size(sizes: List[str]) -> Optional[str]:
    if not sizes:
        return None
    counts = Counter(sizes)
    return counts.most_common(1)[0][0]


def _entropy(sizes: List[str]) -> float:
    if not sizes:
        return 0.0
    counts = Counter(sizes)
    total = len(sizes)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def _bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> float:
    if not height_cm or not weight_kg or height_cm <= 0:
        return 22.0  # population average fallback
    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    return max(10.0, min(60.0, bmi))


# ---------------------------------------------------------------------------
# Main public function — call this for BOTH training and inference
# ---------------------------------------------------------------------------

def build_features(
    user_profile: Optional[FitProfile] = None,
    user_closet: Optional[List[Any]] = None,
    user_feedback: Optional[List[Any]] = None,
    product: Any = None,
    candidate_size: str = "M",
    brand: Optional[Any] = None,
    closet: Optional[List[Any]] = None,
    feedback: Optional[List[Any]] = None,
    *,
    cutoff_timestamp=None,
) -> CandidateRow:
    """
    Build one CandidateRow feature vector for a (user, product, candidate_size) triple.
    Accepts both ORM models and dictionary representations for test/offline script convenience.
    """
    # Normalize closet and feedback parameters
    closet_list = closet if closet is not None else (user_closet or [])
    feedback_list = feedback if feedback is not None else (user_feedback or [])

    # Normalize product and brand attributes
    if isinstance(product, dict):
        category = product.get("category", "tops").lower()
        silhouette_type = product.get("silhouette", product.get("silhouette_type", "regular")).lower()
        brand_name = product.get("brand", "").lower()
        brand_relative_fit = float(product.get("brand_relative_fit", 0.0))
        structure_level = product.get("structure_level", "medium").lower()
    else:
        category = (product.category if product and hasattr(product, "category") else "tops").lower()
        silhouette_type = (product.silhouette_type if product and hasattr(product, "silhouette_type") else "regular").lower()
        brand_name = brand.name.lower() if brand and hasattr(brand, "name") else ""
        brand_relative_fit = brand.relative_fit if brand and hasattr(brand, "relative_fit") else 0.0
        structure_level = (product.structure_level if product and hasattr(product, "structure_level") else "medium").lower()

    is_bot = _is_bottom(category)
    scale = _get_scale(category)

    # ── Filter by cutoff (leakage prevention) ───────────────────────────────
    if cutoff_timestamp is not None:
        closet_list = [c for c in closet_list if getattr(c, "created_at", None) and getattr(c, "created_at") < cutoff_timestamp]
        feedback_list = [f for f in feedback_list if getattr(f, "created_at", None) and getattr(f, "created_at") < cutoff_timestamp]

    # ── User features ────────────────────────────────────────────────────────
    height_cm = getattr(user_profile, "height_cm", None) or 170.0
    weight_kg = getattr(user_profile, "weight_kg", None) or 70.0
    bmi = _bmi(height_cm, weight_kg)

    pref_top = getattr(user_profile, "preferred_top_fit", "regular")
    pref_bottom = getattr(user_profile, "preferred_bottom_fit", "straight")

    pref_enc = (
        BOTTOM_FIT_ENC.get(pref_bottom, 1)
        if is_bot
        else TOP_FIT_ENC.get(pref_top, 1)
    )

    # ── Closet features ──────────────────────────────────────────────────────
    def _get_item_cat(c):
        return (c.get("category") if isinstance(c, dict) else getattr(c, "category", "")).lower()

    def _get_item_brand(c):
        return (c.get("brand") if isinstance(c, dict) else getattr(c, "brand_name", "")).lower()

    def _get_item_rating(c):
        return c.get("fit_rating") if isinstance(c, dict) else getattr(c, "fit_rating", "")

    def _get_item_size(c):
        return c.get("size_label", c.get("size")) if isinstance(c, dict) else getattr(c, "size_label", "")

    cat_closet = [c for c in closet_list if _get_item_cat(c) == category]
    brand_closet = [c for c in closet_list if _get_item_brand(c) == brand_name]

    cat_sizes = [_get_item_size(c) for c in cat_closet if _get_item_size(c)]
    brand_sizes = [_get_item_size(c) for c in brand_closet if _get_item_size(c)]
    cat_mode = _mode_size(cat_sizes)
    brand_mode = _mode_size(brand_sizes)

    perfect_count = sum(1 for c in cat_closet if _get_item_rating(c) == "perfect")
    slightly_tight_count = sum(1 for c in cat_closet if _get_item_rating(c) in ["a_little_tight", "too_tight"])
    slightly_loose_count = sum(1 for c in cat_closet if _get_item_rating(c) in ["a_little_loose", "too_loose"])

    # ── Feedback/purchase features ───────────────────────────────────────────
    def _get_fb_cat(f):
        if isinstance(f, dict):
            return f.get("category", "").lower()
        if hasattr(f, "purchase") and f.purchase and f.purchase.variant and f.purchase.variant.product:
            return f.purchase.variant.product.category.lower()
        return ""

    def _get_fb_brand(f):
        if isinstance(f, dict):
            return f.get("brand", "").lower()
        if hasattr(f, "purchase") and f.purchase and f.purchase.variant and f.purchase.variant.product and f.purchase.variant.product.brand:
            return f.purchase.variant.product.brand.name.lower()
        return ""

    def _get_fb_outcome(f):
        if isinstance(f, dict):
            return f.get("outcome", f.get("outcome_label", ""))
        return getattr(f, "outcome_label", "")

    def _get_fb_reason(f):
        if isinstance(f, dict):
            return f.get("reason", f.get("reason_label", f.get("outcome", "")))
        return getattr(f, "reason_label", "")

    all_fb = feedback_list
    cat_fb = [f for f in all_fb if _get_fb_cat(f) == category]
    brand_fb = [f for f in all_fb if _get_fb_brand(f) == brand_name]

    total_purchases = len(all_fb)
    category_purchases = len(cat_fb)
    brand_purchases = len(brand_fb)

    successful = sum(1 for f in all_fb if _get_fb_outcome(f) in ["kept", "perfect"])
    returned = sum(1 for f in all_fb if _get_fb_outcome(f) == "returned")

    too_tight_count = sum(1 for f in all_fb if _get_fb_reason(f) == "too_tight")
    too_loose_count = sum(1 for f in all_fb if _get_fb_reason(f) == "too_loose")
    brand_too_tight = sum(1 for f in brand_fb if _get_fb_reason(f) == "too_tight")
    brand_too_loose = sum(1 for f in brand_fb if _get_fb_reason(f) == "too_loose")

    brand_success = sum(1 for f in brand_fb if _get_fb_outcome(f) in ["kept", "perfect"])
    cat_success = sum(1 for f in cat_fb if _get_fb_outcome(f) in ["kept", "perfect"])

    # ── Candidate size features ──────────────────────────────────────────────
    cand_numeric = _size_to_numeric(candidate_size, scale)
    cand_position = cand_numeric / max(1.0, float(len(scale) - 1))

    user_mode_numeric = _size_to_numeric(cat_mode, scale) if cat_mode else cand_numeric
    brand_mode_numeric = _size_to_numeric(brand_mode, scale) if brand_mode else cand_numeric

    delta_from_user_mode = cand_numeric - user_mode_numeric
    delta_from_brand_mode = cand_numeric - brand_mode_numeric

    return CandidateRow(
        # User
        height_cm=height_cm,
        weight_kg=weight_kg,
        bmi=bmi,
        preferred_top_fit_enc=TOP_FIT_ENC.get(pref_top, 1),
        preferred_bottom_fit_enc=BOTTOM_FIT_ENC.get(pref_bottom, 1),
        # Closet aggregates
        closet_item_count=len(closet_list),
        category_closet_count=len(cat_closet),
        category_mode_size_numeric=user_mode_numeric,
        category_size_entropy=_entropy(cat_sizes),
        same_brand_item_count=len(brand_closet),
        same_brand_mode_size_numeric=brand_mode_numeric,
        perfect_fit_count=perfect_count,
        slightly_tight_count=slightly_tight_count,
        slightly_loose_count=slightly_loose_count,
        # Feedback aggregates
        total_purchases=total_purchases,
        category_purchases=category_purchases,
        brand_purchases=brand_purchases,
        successful_fit_count=successful,
        return_count=returned,
        too_tight_count=too_tight_count,
        too_loose_count=too_loose_count,
        brand_too_tight_count=brand_too_tight,
        brand_too_loose_count=brand_too_loose,
        brand_fit_success_rate=_safe_rate(brand_success, brand_purchases),
        category_fit_success_rate=_safe_rate(cat_success, category_purchases),
        user_fit_success_rate=_safe_rate(successful, total_purchases),
        # Product
        category_enc=CATEGORY_ENC.get(category, CATEGORY_ENC["other"]),
        silhouette_enc=SILHOUETTE_ENC.get(silhouette_type, SILHOUETTE_ENC["other"]),
        brand_relative_fit=brand_relative_fit,
        available_size_count=len(scale),
        structure_level_enc=STRUCTURE_ENC.get(structure_level, 1),
        # Candidate
        candidate_size_numeric=cand_numeric,
        candidate_size_position=cand_position,
        candidate_size_delta_from_user_mode=delta_from_user_mode,
        candidate_size_delta_from_brand_mode=delta_from_brand_mode,
    )


def build_feature_matrix(
    user_profile: Optional[FitProfile] = None,
    user_closet: Optional[List[Any]] = None,
    user_feedback: Optional[List[Any]] = None,
    product: Any = None,
    candidate_sizes: Optional[List[str]] = None,
    brand: Optional[Any] = None,
    closet: Optional[List[Any]] = None,
    feedback: Optional[List[Any]] = None,
    *,
    cutoff_timestamp=None,
) -> Tuple[List[List[float]], List[str]]:
    """
    Build a feature matrix for all candidate sizes.
    """
    sizes_to_process = candidate_sizes or ["M"]
    matrix = []
    sizes = []
    for size in sizes_to_process:
        row = build_features(
            user_profile=user_profile,
            user_closet=user_closet,
            user_feedback=user_feedback,
            product=product,
            candidate_size=size,
            brand=brand,
            closet=closet,
            feedback=feedback,
            cutoff_timestamp=cutoff_timestamp,
        )
        matrix.append(row.to_list())
        sizes.append(size)
    return matrix, sizes
