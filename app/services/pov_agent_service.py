"""
POVAgentService — Agentic Orchestration Layer

Responsible for:
  - Checking the GEMINI_AGENT_ENABLED feature flag
  - Collecting structured evidence from deterministic pipeline outputs
  - Calling GeminiService for reasoning/explanation
  - Validating and merging Gemini output into the recommendation result
  - Returning the deterministic result untouched if Gemini is disabled or fails

Architecture contract:
  - This service NEVER changes fit_score, recommended_size, cultural_score,
    or any other deterministic signal.
  - If this service raises an exception for any reason, the caller (route)
    should still return the original deterministic result.
  - Gemini is purely additive: it appends `gemini_explanation` and
    `agent_status` to the existing result dict.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _agent_enabled() -> bool:
    """Read feature flag at call time (supports runtime env changes in tests)."""
    return os.environ.get("GEMINI_AGENT_ENABLED", "true").lower() in ("true", "1", "yes")


def _build_evidence(
    deterministic_result: Dict[str, Any],
    profile,
    product,
) -> Dict[str, Any]:
    """
    Assemble structured evidence from deterministic outputs.
    Only includes data already computed by the existing pipeline.
    No new API calls are made here.
    """
    # ── User Profile ──────────────────────────────────────────────────────────
    user_profile: Dict[str, Any] = {}
    if profile:
        user_profile = {
            "preferred_top_fit": getattr(profile, "preferred_top_fit", None),
            "preferred_bottom_fit": getattr(profile, "preferred_bottom_fit", None),
            "preferred_jacket_fit": getattr(profile, "preferred_jacket_fit", None),
            "aesthetic_preference": getattr(profile, "aesthetic_preference", None),
            "occasions": getattr(profile, "occasions", []) or [],
            "budget_tier": getattr(profile, "budget_tier", None),
            "cultural_interests": getattr(profile, "cultural_interests", []) or [],
            "style_expression": getattr(profile, "style_expression", None),
            "calibration_level": getattr(profile, "calibration_level", None),
            "profile_completeness": getattr(profile, "profile_completeness", None),
            "comfort_preferences": getattr(profile, "comfort_preferences", []) or [],
        }

    # ── Product ───────────────────────────────────────────────────────────────
    product_info: Dict[str, Any] = {}
    if product:
        product_info = {
            "name": getattr(product, "name", None),
            "category": getattr(product, "category", None),
            "subcategory": getattr(product, "subcategory", None),
            "price": float(getattr(product, "price", 0) or 0),
            "currency": getattr(product, "currency", "USD"),
            "silhouette_type": getattr(product, "silhouette_type", None),
            "structure_level": getattr(product, "structure_level", None),
            "color_family": getattr(product, "color_family", None),
            "fabric_drape": getattr(product, "fabric_drape", None),
            "description": (getattr(product, "description", None) or "")[:300],
            "brand": getattr(product.brand, "name", None) if getattr(product, "brand", None) else None,
        }

    # ── ML Signals (from existing engine output) ──────────────────────────────
    ml_signals = {
        "recommended_size": deterministic_result.get("recommended_size"),
        "physical_fit_score": deterministic_result.get("physical_fit_score"),
        "fit_prediction": deterministic_result.get("fit_prediction"),
        "fit_probability": deterministic_result.get("fit_probability"),
        "confidence": deterministic_result.get("confidence"),
        "model_version": deterministic_result.get("model_version"),
        "recommendation_source": deterministic_result.get("recommendation_source", "rule"),
    }

    # ── Qloo Cultural Signals ─────────────────────────────────────────────────
    qloo_signals = {
        "cultural_score": deterministic_result.get("cultural_score"),
        "cultural_match_level": deterministic_result.get("cultural_match_level"),
        "cultural_rationale": deterministic_result.get("cultural_rationale"),
        "matched_tags": deterministic_result.get("matched_tags", []),
        "editorial_headline": deterministic_result.get("editorial_headline"),
        "is_qloo_sandbox": deterministic_result.get("is_qloo_sandbox", True),
    }

    return {
        "user_profile": user_profile,
        "product": product_info,
        "ml_signals": ml_signals,
        "qloo_signals": qloo_signals,
        "composite_score": deterministic_result.get("fit_score"),
        "recommendation_mode": deterministic_result.get("recommendation_type", "qloo_enhanced"),
        "existing_explanation_summary": deterministic_result.get("explanation", [])[:3],
    }


class POVAgentService:
    """
    Orchestration service: wraps deterministic POV results with Gemini reasoning.

    Usage (in Flask route):
        analysis = RecommendationService.get_recommendation_for_product(...)
        analysis = POVAgentService.enrich(analysis, profile=profile, product=product)
        return jsonify({"success": True, "data": analysis})
    """

    @staticmethod
    def enrich(
        deterministic_result: Dict[str, Any],
        *,
        profile=None,
        product=None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attempt to enrich a deterministic recommendation with Gemini explanation.

        Always returns a dict. On any failure (including Gemini down, disabled,
        quota exceeded) returns the original result with agent_status=fallback/disabled.

        Parameters
        ----------
        deterministic_result : output of RecommendationService.get_recommendation_for_product()
        profile              : FitProfile ORM object (may be None)
        product              : Product ORM object (may be None)
        trace_id             : optional request trace ID for log correlation

        Returns
        -------
        Enriched result dict with `gemini_explanation` and `agent_status` added.
        The original deterministic fields are NEVER modified.
        """
        tid = trace_id or str(uuid.uuid4())[:8]
        result = dict(deterministic_result)  # shallow copy — originals unchanged

        # ── Feature flag check ────────────────────────────────────────────────
        if not _agent_enabled():
            result["agent_status"] = "disabled"
            result["gemini_explanation"] = {
                "source": "deterministic_fallback",
                "summary": (
                    "This item matches your selected preferences based on the available "
                    "fit, product and recommendation signals."
                ),
                "style_reasons": [],
                "cultural_reasons": [],
                "fit_reasons": [],
                "recommendation_factors": [],
                "confidence": "medium",
                "limitations": ["Gemini agent is disabled (GEMINI_AGENT_ENABLED=false)."],
            }
            logger.debug("POV_AGENT trace_id=%s status=disabled", tid)
            return result

        # ── Build evidence ─────────────────────────────────────────────────────
        try:
            evidence = _build_evidence(deterministic_result, profile, product)
        except Exception as exc:
            logger.warning(
                "POV_AGENT trace_id=%s status=fallback reason=evidence_build_failed error=%s",
                tid, type(exc).__name__,
            )
            result["agent_status"] = "fallback"
            result["gemini_explanation"] = _fallback_explanation("evidence_build_failed")
            return result

        # ── Call Gemini via service ────────────────────────────────────────────
        try:
            from app.services.gemini_service import gemini_service

            timeout = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "15"))
            max_retries = int(os.environ.get("GEMINI_MAX_RETRIES", "1"))

            gemini_result = gemini_service.explain(
                evidence,
                trace_id=tid,
                timeout_seconds=timeout,
                max_retries=max_retries,
            )

            if gemini_result.success:
                result["gemini_explanation"] = gemini_result.explanation
                result["agent_status"] = "gemini"
                result["agent_model"] = gemini_result.model_used
                result["agent_latency_ms"] = gemini_result.latency_ms
            else:
                result["gemini_explanation"] = gemini_result.explanation
                result["agent_status"] = "fallback"
                result["agent_failure_reason"] = gemini_result.failure_reason

        except Exception as exc:
            # Absolute safety net — POVAgentService must never break the route
            logger.error(
                "POV_AGENT trace_id=%s status=fallback reason=unexpected_agent_error error=%s",
                tid, type(exc).__name__,
            )
            result["agent_status"] = "fallback"
            result["gemini_explanation"] = _fallback_explanation("unexpected_agent_error")

        return result


def _fallback_explanation(reason: str) -> Dict[str, Any]:
    """Convenience wrapper for deterministic fallback explanation dict."""
    return {
        "source": "deterministic_fallback",
        "summary": (
            "This item matches your selected preferences based on the available "
            "fit, product and recommendation signals."
        ),
        "style_reasons": [],
        "cultural_reasons": [],
        "fit_reasons": [],
        "recommendation_factors": [],
        "confidence": "medium",
        "limitations": [f"Gemini explanation unavailable: {reason}"],
    }
