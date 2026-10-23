"""
Qloo Cultural Intelligence Service.

Provides taste graph mapping, cross-domain cultural correlations (music, art, film to fashion),
and editorial stylist explainability ("Why this fits your POV").

Supports an embedded Sandbox Mode when QLOO_API_KEY is pending or absent,
allowing full local development and evaluation without requiring live API credentials.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# ── Embedded Cultural Intelligence Graph (Sandbox Knowledge Base) ───────────
CULTURAL_TASTE_PROFILES: Dict[str, Dict[str, Any]] = {
    "streetwear": {
        "correlated_music": ["Hip Hop / Trap", "Electronic / Techno", "Grime", "R&B"],
        "aligned_brands": ["Nike", "Adidas", "Stussy", "Supreme", "Zara"],
        "favored_silhouettes": ["oversized", "relaxed"],
        "favored_structures": ["soft", "balanced"],
        "favored_colors": ["neutral", "dark", "bold"],
        "favored_drapes": ["heavy", "fluid"],
        "editorial_keywords": ["urban utility", "relaxed silhouette", "street-ready comfort"],
        "vibe_headline": "Modern Streetwear & Urban Rhythm",
    },
    "minimalist": {
        "correlated_music": ["Indie Rock", "Ambient / Electronic", "Modern Classical", "Jazz / Soul"],
        "aligned_brands": ["Zara", "COS", "Uniqlo", "H&M"],
        "favored_silhouettes": ["regular", "slim", "straight"],
        "favored_structures": ["structured", "balanced"],
        "favored_colors": ["neutral", "light", "white", "black", "grey"],
        "favored_drapes": ["stiff", "fluid"],
        "editorial_keywords": ["clean architectural lines", "understated elegance", "monochrome harmony"],
        "vibe_headline": "Architectural Minimalism & Thoughtful Restraint",
    },
    "gorpcore": {
        "correlated_music": ["Indie Folk", "Psychedelic Rock", "Electronic", "Outdoor Ambient"],
        "aligned_brands": ["Patagonia", "The North Face", "Arc'teryx", "Adidas", "Nike"],
        "favored_silhouettes": ["relaxed", "regular"],
        "favored_structures": ["structured", "soft"],
        "favored_colors": ["neutral", "earth", "dark", "blue", "grey"],
        "favored_drapes": ["heavy", "stiff"],
        "editorial_keywords": ["technical utility", "functional resilience", "organic textures"],
        "vibe_headline": "Functional Utility & Alpine Earth Tones",
    },
    "vintage": {
        "correlated_music": ["Classic Rock", "Jazz / Soul", "90s Alternative", "Soul / Funk"],
        "aligned_brands": ["Levi's", "Carhartt", "Patagonia", "Zara"],
        "favored_silhouettes": ["straight", "regular", "relaxed"],
        "favored_structures": ["structured"],
        "favored_colors": ["blue", "neutral", "dark"],
        "favored_drapes": ["stiff", "heavy"],
        "editorial_keywords": ["heritage craftsmanship", "timeless drape", "authentic patina"],
        "vibe_headline": "Heritage Workwear & Timeless Patina",
    },
    "quiet luxury": {
        "correlated_music": ["Modern Classical", "Neo-Soul", "Bossa Nova", "Indie Ambient"],
        "aligned_brands": ["Zara", "COS", "Brunello Cucinelli", "Loro Piana", "Patagonia"],
        "favored_silhouettes": ["regular", "straight", "slim"],
        "favored_structures": ["structured", "soft"],
        "favored_colors": ["neutral", "light", "white", "grey"],
        "favored_drapes": ["heavy", "fluid"],
        "editorial_keywords": ["tactile refinement", "unbranded quality", "subtle luxury"],
        "vibe_headline": "Sartorial Composure & Tactile Refinement",
    },
    "casual": {
        "correlated_music": ["Pop", "Indie Rock", "R&B", "Hip Hop / Trap"],
        "aligned_brands": ["H&M", "Nike", "Levi's", "Adidas", "Zara"],
        "favored_silhouettes": ["regular", "relaxed", "straight"],
        "favored_structures": ["soft", "balanced"],
        "favored_colors": ["neutral", "light", "dark", "blue", "white"],
        "favored_drapes": ["fluid", "heavy"],
        "editorial_keywords": ["effortless rotation", "everyday ease", "versatile staple"],
        "vibe_headline": "Effortless Everyday Versatility",
    },
}

MUSIC_AESTHETIC_BRIDGES: Dict[str, str] = {
    "hip hop": "streetwear",
    "trap": "streetwear",
    "electronic": "streetwear",
    "techno": "streetwear",
    "indie rock": "minimalist",
    "ambient": "minimalist",
    "classical": "quiet luxury",
    "jazz": "vintage",
    "soul": "vintage",
    "classic rock": "vintage",
    "folk": "gorpcore",
    "alternative": "vintage",
}


class QlooService:
    """
    Qloo Cultural Intelligence Client with live API integration and Sandbox Fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        sandbox_mode: Optional[bool] = None,
    ):
        self._api_key = (api_key or os.environ.get("QLOO_API_KEY", "")).strip()
        self._base_url = (base_url or os.environ.get("QLOO_API_BASE_URL", "https://hackathon.api.qloo.com")).rstrip("/")
        env_sandbox = os.environ.get("QLOO_SANDBOX_MODE", "false").lower() in ("true", "1", "yes")
        self._sandbox_mode = sandbox_mode if sandbox_mode is not None else env_sandbox

    @property
    def is_sandbox(self) -> bool:
        """Returns True if running in sandbox mode or if no API key is provided."""
        return self._sandbox_mode or not bool(self._api_key)

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def base_url(self) -> str:
        return self._base_url

    def get_cultural_affinities(
        self,
        cultural_interests: Optional[List[str]] = None,
        aesthetic: Optional[str] = None,
        occasions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves cultural affinities and fashion mappings from Qloo or the sandbox graph.
        """
        interests = [i.strip() for i in (cultural_interests or []) if i.strip()]
        aesthetic_key = (aesthetic or "").lower().strip()
        occasions_list = [o.strip() for o in (occasions or []) if o.strip()]

        if not self.is_sandbox:
            try:
                live_res = self._call_qloo_insights(interests, aesthetic_key, occasions_list)
                if live_res:
                    return live_res
            except Exception as e:
                logger.warning(f"Qloo live API call failed, falling back to sandbox: {e}")

        return self._sandbox_cultural_affinities(interests, aesthetic_key, occasions_list)

    def calculate_cultural_resonance(
        self,
        product: Any,
        user_cultural_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Scores the cultural resonance between a product and a user's taste profile.

        Returns:
            resonance_score: float (0.0 to 1.0)
            cultural_match_level: "high" | "medium" | "moderate"
            matched_tags: List[str]
            stylist_rationale: "Why this fits your POV"
            editorial_headline: str
            is_sandbox: bool
        """
        profile = user_cultural_profile or {}
        interests = profile.get("cultural_interests", [])
        aesthetic = (profile.get("aesthetic_preference") or "casual").lower().strip()
        occasions = profile.get("occasions", [])
        style_expression = (profile.get("style_expression") or "").lower().strip()

        # Normalize aesthetic key (style_expression acts as tertiary nudge)
        matched_aesthetic = self._resolve_aesthetic(aesthetic, interests, style_expression)
        cluster = CULTURAL_TASTE_PROFILES.get(matched_aesthetic, CULTURAL_TASTE_PROFILES["casual"])

        # Feature matching score
        score = 0.50  # Base resonance
        matched_elements: List[str] = []

        # 1. Brand affinity match
        brand_name = getattr(product.brand, "name", "") if getattr(product, "brand", None) else ""
        if brand_name and brand_name in cluster["aligned_brands"]:
            score += 0.18
            matched_elements.append(f"{brand_name} cultural alignment")
        elif brand_name:
            score += 0.05

        # 2. Silhouette match
        silhouette = getattr(product, "silhouette_type", "regular") or "regular"
        if silhouette in cluster["favored_silhouettes"]:
            score += 0.14
            matched_elements.append(f"{silhouette.capitalize()} silhouette")
        else:
            score -= 0.04

        # 3. Structure & drape match
        structure = getattr(product, "structure_level", "balanced") or "balanced"
        if structure in cluster["favored_structures"]:
            score += 0.08
            matched_elements.append(f"{structure.capitalize()} structure")

        drape = getattr(product, "fabric_drape", "fluid") or "fluid"
        if drape in cluster["favored_drapes"]:
            score += 0.06
            matched_elements.append(f"{drape.capitalize()} drape")

        # 4. Color family match
        color = getattr(product, "color_family", "neutral") or "neutral"
        if color in cluster["favored_colors"]:
            score += 0.06
            matched_elements.append(f"{color.capitalize()} color palette")

        # Clamp resonance score to [0.25, 0.98]
        final_score = max(0.25, min(0.98, round(score, 2)))

        if final_score >= 0.78:
            match_level = "high"
        elif final_score >= 0.60:
            match_level = "medium"
        else:
            match_level = "moderate"

        # Generate editorial rationale ("Why this fits your POV")
        rationale = self._generate_stylist_rationale(
            product=product,
            cluster=cluster,
            interests=interests,
            aesthetic=matched_aesthetic,
            matched_elements=matched_elements,
            final_score=final_score,
        )

        return {
            "resonance_score": final_score,
            "cultural_match_level": match_level,
            "matched_tags": matched_elements[:4],
            "stylist_rationale": rationale,
            "editorial_headline": cluster["vibe_headline"],
            "is_sandbox": self.is_sandbox,
            "aesthetic_cluster": matched_aesthetic,
        }

    # ── Internal Sandbox Helpers ───────────────────────────────────────────

    def _resolve_aesthetic(self, aesthetic: str, interests: List[str], style_expression: str = "") -> str:
        """Find the closest aesthetic cluster using aesthetic name, music interests, and style expression.
        
        style_expression acts as a soft tertiary signal — it only nudges when a direct
        aesthetic match or music bridge is unavailable, so it remains zero-pressure.
        """
        a_clean = (aesthetic or "").lower().strip()

        # 1. If explicit specific aesthetic is provided (and not generic fallback 'casual')
        if a_clean and a_clean != "casual":
            for key in CULTURAL_TASTE_PROFILES:
                if key in a_clean:
                    return key

        # 2. Check music and cultural interests bridges
        for interest in interests:
            i_lower = interest.lower().strip()
            for genre_keyword, target_aesthetic in MUSIC_AESTHETIC_BRIDGES.items():
                if genre_keyword in i_lower:
                    return target_aesthetic

        # 3. Style expression nudge — maps expression to adjacent aesthetics
        STYLE_EXPRESSION_NUDGE: Dict[str, str] = {
            "feminine": "quiet luxury",
            "masculine": "gorpcore",
            "fluid": "streetwear",
            "nonbinary": "minimalist",
        }
        if style_expression and style_expression in STYLE_EXPRESSION_NUDGE:
            return STYLE_EXPRESSION_NUDGE[style_expression]

        # 4. If aesthetic was explicitly casual or matches a profile
        if a_clean in CULTURAL_TASTE_PROFILES:
            return a_clean

        return "casual"

    def _generate_stylist_rationale(
        self,
        product: Any,
        cluster: Dict[str, Any],
        interests: List[str],
        aesthetic: str,
        matched_elements: List[str],
        final_score: float,
    ) -> str:
        """Constructs a personalised, editorial stylist justification."""
        product_name = getattr(product, "name", "This piece")
        brand_name = getattr(product.brand, "name", "") if getattr(product, "brand", None) else ""
        silhouette = getattr(product, "silhouette_type", "regular") or "regular"

        cultural_anchor = ""
        if interests:
            cultural_anchor = f"your affinity for {', '.join(interests[:2])} and "

        if final_score >= 0.78:
            return (
                f"Chosen by POV because {cultural_anchor}{aesthetic.title()} aesthetics call for "
                f"{cluster['editorial_keywords'][0]}. The {silhouette} cut and {cluster['editorial_keywords'][1]} "
                f"from {brand_name or 'this collection'} express your point of view effortlessly."
            )
        elif final_score >= 0.60:
            return (
                f"Recommended by POV as a versatile wardrobe staple aligning with your {aesthetic.title()} taste profile, "
                f"featuring a clean {silhouette} fit and {cluster['editorial_keywords'][2]}."
            )
        else:
            return (
                f"Curated by POV as a foundational piece that balances your preferred {silhouette} proportions with "
                f"classic, day-to-day versatility."
            )

    def _sandbox_cultural_affinities(
        self,
        interests: List[str],
        aesthetic: str,
        occasions: List[str],
        style_expression: str = "",
    ) -> Dict[str, Any]:
        """Simulates Qloo's taste graph response."""
        resolved = self._resolve_aesthetic(aesthetic, interests, style_expression)
        cluster = CULTURAL_TASTE_PROFILES[resolved]

        return {
            "source": "qloo_sandbox",
            "aesthetic": resolved,
            "headline": cluster["vibe_headline"],
            "correlated_cultural_entities": cluster["correlated_music"] + occasions,
            "aligned_brands": cluster["aligned_brands"],
            "design_cues": {
                "silhouettes": cluster["favored_silhouettes"],
                "structures": cluster["favored_structures"],
                "colors": cluster["favored_colors"],
                "drapes": cluster["favored_drapes"],
            },
            "editorial_keywords": cluster["editorial_keywords"],
        }

    # ── Live Qloo API Integration ──────────────────────────────────────────

    def _request_headers(self) -> Dict[str, str]:
        """Headers used by the Qloo hackathon API."""
        return {
            "X-Api-Key": self._api_key,
            "Accept": "application/json",
        }

    @staticmethod
    def _extract_entities(payload: Any) -> List[Dict[str, Any]]:
        """Handle the common list envelopes returned by Qloo endpoints."""
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        # Search responses commonly use `results`; tolerate other envelopes too.
        for key in ("results", "entities", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = QlooService._extract_entities(value)
                if nested:
                    return nested
        return []

    def _search_entity(self, client: httpx.Client, query: str) -> Optional[Dict[str, Any]]:
        """Resolve a human-readable interest to a Qloo entity UUID."""
        if not query:
            return None

        response = client.get(
            f"{self._base_url}/search",
            headers=self._request_headers(),
            params={"query": query},
        )
        response.raise_for_status()
        payload = response.json()
        entities = self._extract_entities(payload)
        if not entities:
            logger.info("Qloo search returned no entities for interest %r", query)
            return None

        # Prefer a result that has an entity UUID and a name; the first result is
        # generally the closest text match. Search result types vary by entity.
        for entity in entities:
            entity_id = entity.get("entity_id") or entity.get("id")
            if entity_id:
                return {
                    "entity_id": str(entity_id),
                    "name": entity.get("name") or query,
                    "raw": entity,
                }

        logger.info("Qloo search results for %r did not contain entity IDs", query)
        return None

    @staticmethod
    def _entity_name(entity: Dict[str, Any]) -> Optional[str]:
        """Extract a display name from an Insights result."""
        if entity.get("name"):
            return str(entity["name"])
        properties = entity.get("properties")
        if isinstance(properties, dict) and properties.get("name"):
            return str(properties["name"])
        return None

    def _call_qloo_insights(
        self,
        interests: List[str],
        aesthetic: str,
        occasions: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve text interests with `/search`, then request brand insights.

        Qloo Insights expects entity UUIDs in `signal.interests.entities`, not
        free-text interests. A None result tells the caller to use its local
        fallback graph.
        """
        if not self._api_key:
            logger.info("Qloo API key is missing; using local cultural graph")
            return None

        # Use the user's explicit interests as signals. An aesthetic or occasion
        # can also act as a signal when supplied, but don't send empty strings.
        search_terms: List[str] = []
        for term in [*interests, aesthetic, *occasions]:
            clean = (term or "").strip()
            if clean and clean.casefold() not in {x.casefold() for x in search_terms}:
                search_terms.append(clean)

        if not search_terms:
            logger.info("No cultural interests/aesthetic/occasions supplied to Qloo")
            return None

        try:
            with httpx.Client(timeout=12.0) as client:
                resolved: List[Dict[str, Any]] = []
                for term in search_terms[:8]:
                    try:
                        entity = self._search_entity(client, term)
                    except httpx.HTTPStatusError as exc:
                        logger.warning(
                            "Qloo search failed for %r (HTTP %s)",
                            term, exc.response.status_code,
                        )
                        continue
                    except (httpx.HTTPError, ValueError) as exc:
                        logger.warning("Qloo search failed for %r: %s", term, exc)
                        continue
                    if entity and all(
                        existing["entity_id"] != entity["entity_id"] for existing in resolved
                    ):
                        resolved.append(entity)

                if not resolved:
                    logger.warning("Could not resolve any cultural signals with Qloo Search")
                    return None

                params = {
                    "filter.type": "urn:entity:brand",
                    "signal.interests.entities": ",".join(
                        entity["entity_id"] for entity in resolved
                    ),
                    "take": 10,
                }
                response = client.get(
                    f"{self._base_url}/v2/insights",
                    headers=self._request_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    logger.warning("Qloo Insights returned an unexpected response type")
                    return None

                results = self._extract_entities(data)
                brand_names: List[str] = []
                for entity in results:
                    name = self._entity_name(entity)
                    if name and name not in brand_names:
                        brand_names.append(name)

                # Preserve Qloo's complete response while exposing stable fields
                # consumed by the app's existing cultural-affinity interface.
                data["source"] = "qloo_live"
                data["aesthetic"] = self._resolve_aesthetic(aesthetic, interests)
                data["resolved_signals"] = [
                    {"entity_id": entity["entity_id"], "name": entity["name"]}
                    for entity in resolved
                ]
                data["aligned_brands"] = brand_names
                data["correlated_cultural_entities"] = [
                    entity["name"] for entity in resolved
                ]
                data["is_sandbox"] = False
                return data

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Qloo Insights failed (HTTP %s): %s",
                exc.response.status_code, exc.response.text[:500],
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Qloo API request failed: %s", exc)
        except Exception:
            logger.exception("Unexpected error while calling Qloo")
        return None


# Global singleton instance
qloo_service = QlooService()
