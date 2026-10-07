"""
Unit tests for MLRecommendationEngine.
"""

import pytest
from app.recommendation.base import UserHistory
from app.recommendation.ml_engine import MLRecommendationEngine
from app.models.fit_profile import FitProfile


@pytest.fixture
def ml_engine():
    # Will attempt to load models/pov_fit_model.txt; if not found, handles gracefully
    return MLRecommendationEngine(model_path="models/pov_fit_model.txt")


@pytest.fixture
def sample_user_history():
    profile = FitProfile(height_cm=175, weight_kg=70, preferred_top_fit="fitted", preferred_bottom_fit="straight")
    return UserHistory(profile=profile, closet=[], feedback=[])


def test_ml_engine_recommendation_structure(ml_engine, sample_user_history):
    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    result = ml_engine.recommend(user_history=sample_user_history, product=product)

    assert "recommended_size" in result
    assert result["recommended_size"] in product["available_sizes"]
    assert "fit_probability" in result
    assert "explanation" in result
    assert "recommendation_source" in result


def test_ml_engine_respects_available_sizes(ml_engine, sample_user_history):
    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["L"]
    }

    result = ml_engine.recommend(user_history=sample_user_history, product=product)

    assert result["recommended_size"] == "L"
