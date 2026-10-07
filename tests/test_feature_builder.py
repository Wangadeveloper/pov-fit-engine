"""
Unit tests for ML Feature Builder.
"""

import pytest
from app.recommendation.base import UserHistory
from app.models.fit_profile import FitProfile
from ml.feature_builder import build_features
from ml.schemas import CandidateRow


def test_feature_builder_output_shape_and_types():
    profile = FitProfile(height_cm=180, weight_kg=75, preferred_top_fit="fitted", preferred_bottom_fit="straight")
    user_history = UserHistory(profile=profile, closet=[], feedback=[])

    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "TestBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    features = build_features(
        user_profile=user_history.profile,
        closet=user_history.closet,
        feedback=user_history.feedback,
        product=product,
        candidate_size="M"
    )

    assert isinstance(features, CandidateRow)
    feat_dict = features.model_dump()
    assert isinstance(feat_dict, dict)
    assert len(feat_dict) > 20
    assert feat_dict["height_cm"] == 180.0
    assert feat_dict["weight_kg"] == 75.0
    assert feat_dict["bmi"] == pytest.approx(75.0 / (1.8 ** 2), rel=1e-2)
    assert feat_dict["candidate_size_numeric"] == 3.0  # M in TOPS_SCALE ("XXS", "XS", "S", "M", ...) is index 3


def test_feature_builder_determinism():
    profile = FitProfile(height_cm=170, weight_kg=65, preferred_top_fit="relaxed", preferred_bottom_fit="straight")
    user_history = UserHistory(profile=profile, closet=[], feedback=[])

    product = {
        "category": "Bottoms",
        "silhouette": "slim",
        "brand": "BrandY",
        "brand_relative_fit": -0.5,
        "available_sizes": ["30", "32", "34"]
    }

    f1 = build_features(user_history.profile, user_history.closet, user_history.feedback, product, "32")
    f2 = build_features(user_history.profile, user_history.closet, user_history.feedback, product, "32")

    assert f1.model_dump() == f2.model_dump()


def test_feature_builder_cold_start_no_nans():
    profile = FitProfile(height_cm=165, weight_kg=55, preferred_top_fit="regular", preferred_bottom_fit="straight")
    user_history = UserHistory(profile=profile, closet=[], feedback=[])

    product = {
        "category": "Dresses",
        "silhouette": "regular",
        "brand": "BrandZ",
        "brand_relative_fit": 0.0,
        "available_sizes": ["XS", "S", "M"]
    }

    features = build_features(user_history.profile, user_history.closet, user_history.feedback, product, "S")

    for k, v in features.model_dump().items():
        assert v is not None, f"Feature {k} is None"
        if isinstance(v, float):
            import math
            assert not math.isnan(v), f"Feature {k} is NaN"
