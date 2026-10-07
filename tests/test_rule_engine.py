"""
Unit tests for RuleBasedRecommendationEngine.
"""

import pytest
from app.recommendation.base import UserHistory
from app.recommendation.rule_engine import RuleBasedRecommendationEngine
from app.models.fit_profile import FitProfile


@pytest.fixture
def rule_engine():
    return RuleBasedRecommendationEngine()


@pytest.fixture
def sample_user_history():
    profile = FitProfile(
        height_cm=175,
        weight_kg=70,
        preferred_top_fit="fitted",
        preferred_bottom_fit="straight"
    )
    return UserHistory(profile=profile, closet=[], feedback=[])


def test_rule_engine_cold_start(rule_engine, sample_user_history):
    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }
    result = rule_engine.recommend(user_history=sample_user_history, product=product)

    assert "recommended_size" in result
    assert result["recommended_size"] in product["available_sizes"]
    assert "explanation" in result
    assert "rule" in result["recommendation_source"]


def test_rule_engine_brand_bias(rule_engine, sample_user_history):
    # Brand runs small (+1 size needed)
    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "SmallBrand",
        "brand_relative_fit": 1.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }
    result = rule_engine.recommend(user_history=sample_user_history, product=product)
    assert result["recommended_size"] in product["available_sizes"]


def test_rule_engine_unavailable_size_filtering(rule_engine, sample_user_history):
    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["XL"]
    }
    result = rule_engine.recommend(user_history=sample_user_history, product=product)
    assert result["recommended_size"] == "XL"
