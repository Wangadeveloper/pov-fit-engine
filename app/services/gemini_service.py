"""
GeminiService — POV Agentic Intelligence Layer

Responsible ONLY for:
  - Gemini SDK configuration and model invocation
  - Prompt construction from structured evidence
  - Structured JSON response parsing and validation
  - Quota / timeout / network error handling
  - Observability logging (no PII, no API keys)

This service NEVER modifies recommendation scores or product data.
It is purely a reasoning and explanation layer.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Required keys in a valid Gemini explanation response ─────────────────────
_REQUIRED_KEYS = {"summary", "style_reasons", "cultural_reasons", "fit_reasons", "confidence", "limitations"}

# ── Quota / rate-limit error signals from google-generativeai ────────────────
_QUOTA_SIGNALS = (
    "429",
    "quota",
    "rate",
    "resource_exhausted",
    "resourceexhausted",
    "rateLimitExceeded",
    "userRateLimitExceeded",
)


@dataclass
class GeminiResult:
    """Returned by GeminiService.explain(). Always populated — success or failure."""
    success: bool
    explanation: Dict[str, Any]          # structured explanation dict
    failure_reason: Optional[str] = None  # None on success
    latency_ms: int = 0
    model_used: Optional[str] = None


def _is_quota_error(exc: Exception) -> bool:
    """Detect quota / rate-limit errors so we skip retry immediately."""
    msg = str(exc).lower()
    return any(signal in msg for signal in _QUOTA_SIGNALS)


def _build_prompt(evidence: Dict[str, Any]) -> str:
    """
    Construct a grounded, structured prompt from deterministic evidence.

    Gemini is explicitly instructed:
      - Only reason over evidence provided.
      - Do NOT invent scores, cultural tags, or fit measurements.
      - If a signal is unavailable, say so explicitly in limitations.
      - Return only valid JSON — no markdown, no code fences.
    """
    evidence_json = json.dumps(evidence, indent=2, default=str)

    return f"""You are the POV Fashion Intelligence Agent. Your role is to explain why a garment matches a shopper's personal style, using ONLY the evidence provided below. You must NEVER invent data, scores, or cultural associations not present in the evidence.

## Evidence (from deterministic POV pipeline)
```json
{evidence_json}
```

## Task
Based solely on the evidence above, produce a structured fashion explanation. Be specific, grounded, and editorial in tone. Reference actual values from the evidence (e.g., specific aesthetic cluster, silhouette type, fit score, cultural tags).

## Rules
1. Do NOT generate or change any numerical score — the composite_score in the evidence is authoritative.
2. If a signal field is null, missing, or marked unavailable, acknowledge this in `limitations` rather than inventing data.
3. `confidence` must be one of: "high", "medium", or "low" — derived from the evidence `confidence` value (≥0.75 → high, ≥0.50 → medium, else low).
4. Be editorial and warm — like a personal stylist speaking to the shopper.
5. style_reasons, cultural_reasons, fit_reasons, recommendation_factors must each be arrays of short, specific strings (2–5 items each).

## Required JSON Response (no markdown, no code fences, pure JSON only)
{{
  "summary": "One or two sentences explaining why this garment fits this shopper's POV",
  "style_reasons": ["specific style match reason 1", "..."],
  "cultural_reasons": ["specific cultural/taste reason 1 (or 'Cultural data unavailable' if qloo signals absent)", "..."],
  "fit_reasons": ["specific physical fit reason 1", "..."],
  "recommendation_factors": ["key factor driving the recommendation 1", "..."],
  "confidence": "high|medium|low",
  "limitations": ["any missing signals or caveats, or 'None' if fully grounded"]
}}"""


def _validate_response(data: Dict[str, Any]) -> bool:
    """Returns True if the response has all required keys with correct types."""
    if not isinstance(data, dict):
        return False
    if not _REQUIRED_KEYS.issubset(data.keys()):
        return False
    if data.get("confidence") not in ("high", "medium", "low"):
        return False
    for key in ("style_reasons", "cultural_reasons", "fit_reasons", "limitations"):
        if not isinstance(data.get(key), list):
            return False
    return True


def _deterministic_fallback_explanation(reason: str) -> Dict[str, Any]:
    """Safe explanation dict returned when Gemini is unavailable."""
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


class GeminiService:
    """
    Thin wrapper around google-generativeai for POV fit explanations.

    Instantiated lazily — importing this module does NOT require the SDK
    to be installed or the key to be present. If either is missing the
    service degrades gracefully.
    """

    def __init__(self) -> None:
        self._model = None          # lazy-loaded on first call
        self._sdk_available = None  # tri-state: None=unchecked, True/False

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def explain(
        self,
        evidence: Dict[str, Any],
        *,
        trace_id: Optional[str] = None,
        max_retries: int = 1,
        timeout_seconds: int = 15,
    ) -> GeminiResult:
        """
        Send structured evidence to Gemini and return a validated explanation.

        Parameters
        ----------
        evidence        : structured dict built from deterministic pipeline outputs
        trace_id        : optional request ID for logging correlation
        max_retries     : number of retries on *transient* errors (quota → 0 retries)
        timeout_seconds : seconds to wait for Gemini response

        Returns
        -------
        GeminiResult — always populated; .success=False on any failure.
        """
        tid = trace_id or str(uuid.uuid4())[:8]
        t_start = time.monotonic()

        # 1. Check SDK availability
        if not self._ensure_sdk():
            latency = int((time.monotonic() - t_start) * 1000)
            logger.warning(
                "POV_AGENT trace_id=%s status=fallback reason=sdk_unavailable latency_ms=%d",
                tid, latency,
            )
            return GeminiResult(
                success=False,
                explanation=_deterministic_fallback_explanation("google-generativeai SDK not installed"),
                failure_reason="sdk_unavailable",
                latency_ms=latency,
            )

        # 2. Check API key
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            latency = int((time.monotonic() - t_start) * 1000)
            logger.warning(
                "POV_AGENT trace_id=%s status=fallback reason=no_api_key latency_ms=%d",
                tid, latency,
            )
            return GeminiResult(
                success=False,
                explanation=_deterministic_fallback_explanation("GEMINI_API_KEY not configured"),
                failure_reason="no_api_key",
                latency_ms=latency,
            )

        # 3. Build prompt
        prompt = _build_prompt(evidence)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

        # 4. Attempt call (with limited retries on transient errors)
        attempts = 0
        last_exc: Optional[Exception] = None

        while attempts <= max_retries:
            attempts += 1
            try:
                result = self._call_gemini(prompt, api_key, model_name, timeout_seconds, tid)
                latency = int((time.monotonic() - t_start) * 1000)
                logger.info(
                    "POV_AGENT trace_id=%s status=success model=%s latency_ms=%d "
                    "qloo_available=%s ml_available=%s",
                    tid, model_name, latency,
                    bool(evidence.get("qloo_signals")),
                    bool(evidence.get("ml_signals")),
                )
                result.latency_ms = latency
                return result

            except Exception as exc:
                last_exc = exc
                is_quota = _is_quota_error(exc)
                failure_reason = "quota_exceeded" if is_quota else "transient_error"

                logger.warning(
                    "POV_AGENT trace_id=%s status=error attempt=%d/%d reason=%s error=%s",
                    tid, attempts, max_retries + 1, failure_reason,
                    type(exc).__name__,
                )

                # Never retry quota errors
                if is_quota:
                    break

                # Don't sleep on last attempt
                if attempts <= max_retries:
                    time.sleep(0.5)

        # 5. All attempts exhausted — fallback
        latency = int((time.monotonic() - t_start) * 1000)
        reason = "quota_exceeded" if _is_quota_error(last_exc) else "api_error"
        logger.warning(
            "POV_AGENT trace_id=%s status=fallback reason=%s fallback=deterministic latency_ms=%d",
            tid, reason, latency,
        )
        return GeminiResult(
            success=False,
            explanation=_deterministic_fallback_explanation(reason),
            failure_reason=reason,
            latency_ms=latency,
            model_used=model_name,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _ensure_sdk(self) -> bool:
        """Returns True if google-generativeai is importable."""
        if self._sdk_available is not None:
            return self._sdk_available
        try:
            import google.generativeai  # noqa: F401
            self._sdk_available = True
        except ImportError:
            self._sdk_available = False
            logger.error("POV_AGENT google-generativeai not installed. Run: pip install google-generativeai")
        return self._sdk_available

    def _get_model(self, api_key: str, model_name: str):
        """Lazy-load and cache the GenerativeModel."""
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": 0.3,        # low temp for grounded, consistent output
                "top_p": 0.8,
                "max_output_tokens": 800,  # explanation shouldn't be a novel
                "response_mime_type": "application/json",
            },
        )

    def _call_gemini(
        self,
        prompt: str,
        api_key: str,
        model_name: str,
        timeout_seconds: int,
        trace_id: str,
    ) -> GeminiResult:
        """
        Make the actual Gemini API call.
        Raises exception on any failure — caller handles retry/fallback.
        """
        import google.generativeai as genai

        model = self._get_model(api_key, model_name)

        # google-generativeai uses request_options for timeout
        response = model.generate_content(
            prompt,
            request_options={"timeout": timeout_seconds},
        )

        raw_text = response.text.strip()

        # Strip markdown code fences if model ignored the instruction
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            # Remove first and last fence lines
            raw_text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "POV_AGENT trace_id=%s status=error reason=invalid_json snippet=%s",
                trace_id, raw_text[:120],
            )
            return GeminiResult(
                success=False,
                explanation=_deterministic_fallback_explanation("invalid_json"),
                failure_reason="invalid_json",
                model_used=model_name,
            )

        if not _validate_response(data):
            missing = _REQUIRED_KEYS - set(data.keys())
            logger.warning(
                "POV_AGENT trace_id=%s status=error reason=schema_validation_failed missing_keys=%s",
                trace_id, missing,
            )
            return GeminiResult(
                success=False,
                explanation=_deterministic_fallback_explanation("schema_validation_failed"),
                failure_reason="schema_validation_failed",
                model_used=model_name,
            )

        data["source"] = "gemini"
        return GeminiResult(
            success=True,
            explanation=data,
            failure_reason=None,
            model_used=model_name,
        )


# ── Module-level singleton ────────────────────────────────────────────────────
gemini_service = GeminiService()
