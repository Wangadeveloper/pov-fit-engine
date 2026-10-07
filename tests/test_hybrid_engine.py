"""
Unit tests for HybridRecommendationEngine.
"""

import pytest
from app.recommendation.base import UserHistory, RecommendationEngine
from app.recommendation.rule_engine import RuleBasedRecommendationEngine
from app.recommendation.ml_engine import MLRecommendationEngine
from app.recommendation.hybrid_engine import HybridRecommendationEngine
from app.models.fit_profile import FitProfile


class MockEngine(RecommendationEngine):
    def __init__(self, size="L", confidence=0.8, is_available=True):
        self.size = size
        self.confidence = confidence
        self._is_available = is_available

    def is_available(self):
        return self._is_available

    def recommend(
        self,
        user_profile=None,
        user_closet=None,
        user_feedback=None,
        product=None,
        variants=None,
        brand=None,
        user_history=None,
        **kwargs
    ):
        if not self._is_available:
            return {
                "recommended_size": self.size,
                "confidence_score": "Low",
                "confidence": 0.25,
                "fit_probability": None,
                "explanation": "Model unavailable",
                "recommendation_source": "rule"
            }
        return {
            "recommended_size": self.size,
            "confidence_score": "High" if self.confidence > 0.7 else "Low",
            "confidence": self.confidence,
            "fit_probability": self.confidence,
            "explanation": "Mock recommendation",
            "recommendation_source": "ml",
            "model_version": "v1.0.0",
            "all_scores": {self.size: self.confidence}
        }


@pytest.fixture
def sample_user_history():
    profile = FitProfile(height_cm=175, weight_kg=70, preferred_top_fit="fitted", preferred_bottom_fit="straight")
    return UserHistory(profile=profile, closet=[], feedback=[])


def test_hybrid_engine_high_confidence(sample_user_history):
    mock_ml = MockEngine(size="M", confidence=0.85, is_available=True)
    rule = RuleBasedRecommendationEngine()
    hybrid = HybridRecommendationEngine(ml_engine=mock_ml, rule_engine=rule, min_confidence=0.55)

    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    result = hybrid.recommend(sample_user_history, product)
    assert result["recommended_size"] == "M"
    assert "ml" in result["recommendation_source"] or "hybrid" in result["recommendation_source"]


def test_hybrid_engine_low_confidence_fallback(sample_user_history):
    mock_ml = MockEngine(size="M", confidence=0.30, is_available=True)
    rule = RuleBasedRecommendationEngine()
    hybrid = HybridRecommendationEngine(ml_engine=mock_ml, rule_engine=rule, min_confidence=0.55)

    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    result = hybrid.recommend(sample_user_history, product)
    assert "rule" in result["recommendation_source"]


def test_hybrid_engine_model_unavailable_fallback(sample_user_history):
    mock_ml = MockEngine(size="M", confidence=0.85, is_available=False)
    rule = RuleBasedRecommendationEngine()
    hybrid = HybridRecommendationEngine(ml_engine=mock_ml, rule_engine=rule, min_confidence=0.55)

    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    result = hybrid.recommend(sample_user_history, product)
    assert "rule" in result["recommendation_source"]


def test_hybrid_engine_guardrail_unavailable_size(sample_user_history):
    # ML recommends size XXL which is not available
    mock_ml = MockEngine(size="XXL", confidence=0.90, is_available=True)
    rule = RuleBasedRecommendationEngine()
    hybrid = HybridRecommendationEngine(ml_engine=mock_ml, rule_engine=rule, min_confidence=0.55)

    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "StandardBrand",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    result = hybrid.recommend(sample_user_history, product)
    assert result["recommended_size"] in product["available_sizes"]
