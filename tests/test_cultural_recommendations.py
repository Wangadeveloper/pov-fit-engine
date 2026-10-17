"""
Integration tests for POV Cultural Stylist Recommendation Service and A/B Evaluation.
"""
import uuid
import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.fit_profile import FitProfile
from app.services.recommendation_service import RecommendationService


@pytest.fixture
def app_ctx():
    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        # Query seeded product from _init_db_data
        prod = db.session.query(Product).first()
        assert prod is not None

        # Seed test user & cultural fit profile
        user = User(
            email=f"test_{uuid.uuid4().hex[:6]}@pov.style",
            hashed_password="mockhashedpassword",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        profile = FitProfile(
            user_id=user.id,
            preferred_top_fit="regular",
            preferred_bottom_fit="straight",
            preferred_jacket_fit="regular",
            comfort_preferences=["Stretch"],
            cultural_interests=["Hip Hop / Trap", "Electronic / Techno"],
            aesthetic_preference="streetwear",
            occasions=["Daily Casual"],
            confidence=0.8,
            profile_completeness=0.9,
        )
        db.session.add(profile)
        db.session.commit()

        yield app, user, prod

        # Cleanup test user and profile
        db.session.delete(profile)
        db.session.delete(user)
        db.session.commit()


def test_qloo_enhanced_vs_standard_batch(app_ctx):
    app, user, prod = app_ctx

    # 1. Standard Recommendations (Control)
    standard_recs = RecommendationService.get_recommendations_for_products_batch(
        db, user.id, [prod], recommendation_mode="standard"
    )
    assert len(standard_recs) == 1
    std = standard_recs[0]
    assert std["recommendation_type"] == "standard"
    assert "recommended_size" in std
    assert std["fit_score"] > 0

    # 2. Qloo-Enhanced Recommendations (Cultural Stylist)
    qloo_recs = RecommendationService.get_recommendations_for_products_batch(
        db, user.id, [prod], recommendation_mode="qloo_enhanced"
    )
    assert len(qloo_recs) == 1
    q = qloo_recs[0]
    assert q["recommendation_type"] == "qloo_enhanced"
    assert q["cultural_score"] is not None
    assert 0.0 <= q["cultural_score"] <= 1.0
    assert "cultural_rationale" in q
    assert len(q["cultural_rationale"]) > 0
    assert any("POV Stylist" in exp for exp in q["explanation"])


def test_compare_recommendations_metrics(app_ctx):
    app, user, prod = app_ctx

    comparison = RecommendationService.compare_recommendations(
        db, user.id, [prod]
    )
    assert comparison["product_count"] == 1
    assert "evaluation_metrics" in comparison
    metrics = comparison["evaluation_metrics"]
    assert "avg_standard_score" in metrics
    assert "avg_qloo_score" in metrics
    assert "score_delta" in metrics
    assert "avg_cultural_resonance" in metrics
    assert "personalization_lift_pct" in metrics
