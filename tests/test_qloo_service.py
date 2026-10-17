"""
Unit tests for Qloo Cultural Intelligence Service and Sandbox Engine.
"""
import pytest
from app.services.qloo_service import QlooService, CULTURAL_TASTE_PROFILES


class MockProduct:
    def __init__(
        self,
        name="Club Fleece Hoodie",
        brand_name="Nike",
        silhouette="relaxed",
        structure="soft",
        drape="heavy",
        color="neutral",
        category="Hoodies",
    ):
        self.name = name
        self.silhouette_type = silhouette
        self.structure_level = structure
        self.fabric_drape = drape
        self.color_family = color
        self.category = category
        self.brand = type("Brand", (), {"name": brand_name})()


def test_qloo_sandbox_mode_when_no_api_key():
    service = QlooService(api_key="", sandbox_mode=True)
    assert service.is_sandbox is True


def test_qloo_cultural_affinities_sandbox():
    service = QlooService(api_key="", sandbox_mode=True)
    affinities = service.get_cultural_affinities(
        cultural_interests=["Hip Hop / Trap"],
        aesthetic="streetwear",
        occasions=["Daily Casual"],
    )
    assert affinities["source"] == "qloo_sandbox"
    assert affinities["aesthetic"] == "streetwear"
    assert "Nike" in affinities["aligned_brands"]
    assert "oversized" in affinities["design_cues"]["silhouettes"]


def test_qloo_aesthetic_resolution_via_music():
    service = QlooService(api_key="", sandbox_mode=True)
    # User didn't specify aesthetic, but specified Indie Rock
    res = service.calculate_cultural_resonance(
        product=MockProduct(),
        user_cultural_profile={
            "cultural_interests": ["Indie Rock"],
            "aesthetic_preference": "",
        },
    )
    assert res["aesthetic_cluster"] == "minimalist"
    assert "Why this fits your POV" in res["stylist_rationale"] or "POV" in res["stylist_rationale"]


def test_qloo_resonance_high_match():
    service = QlooService(api_key="", sandbox_mode=True)
    # Streetwear product with Nike + relaxed silhouette
    product = MockProduct(brand_name="Nike", silhouette="relaxed", structure="soft", drape="heavy")
    res = service.calculate_cultural_resonance(
        product=product,
        user_cultural_profile={
            "cultural_interests": ["Hip Hop / Trap", "Electronic / Techno"],
            "aesthetic_preference": "streetwear",
        },
    )
    assert res["resonance_score"] >= 0.70
    assert res["cultural_match_level"] in ("high", "medium")
    assert len(res["matched_tags"]) > 0
    assert "streetwear" in res["stylist_rationale"].lower() or "urban" in res["stylist_rationale"].lower()


def test_qloo_resonance_bounds():
    service = QlooService(api_key="", sandbox_mode=True)
    product = MockProduct(brand_name="Unknown", silhouette="exotic")
    res = service.calculate_cultural_resonance(
        product=product,
        user_cultural_profile={"aesthetic_preference": "vintage"},
    )
    # Score should always be valid and clamped
    assert 0.25 <= res["resonance_score"] <= 0.98
    assert isinstance(res["stylist_rationale"], str)
    assert len(res["stylist_rationale"]) > 10
