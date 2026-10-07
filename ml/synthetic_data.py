"""
Synthetic data generator for POV ML training.

Generates realistic users, products, and purchase interactions with
probabilistic fit outcomes — NOT derived from the rule engine.

Usage::

    python -m ml.synthetic_data

Output:
    data/synthetic_users.parquet
    data/synthetic_products.parquet
    data/synthetic_interactions.parquet
    data/training_dataset.parquet
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOPS_SCALE = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]
BOTTOMS_SCALE = ["26", "28", "29", "30", "31", "32", "33", "34", "36", "38", "40"]

CATEGORIES = {
    "T-Shirts":  {"scale": "tops",    "silhouettes": ["slim", "regular", "relaxed", "oversized"]},
    "Shirts":    {"scale": "tops",    "silhouettes": ["slim", "regular"]},
    "Hoodies":   {"scale": "tops",    "silhouettes": ["regular", "relaxed", "oversized"]},
    "Sweaters":  {"scale": "tops",    "silhouettes": ["regular", "relaxed", "oversized"]},
    "Jackets":   {"scale": "tops",    "silhouettes": ["slim", "regular", "oversized"]},
    "Jeans":     {"scale": "bottoms", "silhouettes": ["slim", "straight", "relaxed"]},
    "Trousers":  {"scale": "bottoms", "silhouettes": ["slim", "straight", "relaxed"]},
    "Shorts":    {"scale": "bottoms", "silhouettes": ["regular", "relaxed"]},
}

BRAND_PROFILES = [
    {"name": "NovaFit",    "relative_fit": -0.8, "noise": 0.15},
    {"name": "Zander",     "relative_fit": -0.5, "noise": 0.20},
    {"name": "StdWear",    "relative_fit":  0.0, "noise": 0.10},
    {"name": "UrbanBase",  "relative_fit":  0.0, "noise": 0.15},
    {"name": "CoreStyle",  "relative_fit":  0.1, "noise": 0.20},
    {"name": "LooseFit",   "relative_fit":  0.5, "noise": 0.20},
    {"name": "Broadline",  "relative_fit":  0.8, "noise": 0.15},
    {"name": "StreetFlex", "relative_fit": -0.3, "noise": 0.25},
    {"name": "PremiumCo",  "relative_fit":  0.0, "noise": 0.08},
    {"name": "Casuals",    "relative_fit":  0.2, "noise": 0.30},
    {"name": "SportFit",   "relative_fit": -0.4, "noise": 0.15},
    {"name": "NaturalCut", "relative_fit":  0.3, "noise": 0.20},
]

TOP_FIT_PREFS = ["fitted", "slim", "regular", "relaxed", "oversized"]
BOTTOM_FIT_PREFS = ["slim", "straight", "regular", "relaxed"]

SILHOUETTE_OFFSET: Dict[str, float] = {
    "oversized": 1.5,
    "relaxed": 0.7,
    "regular": 0.0,
    "straight": 0.0,
    "slim": -0.7,
}

PREF_OFFSET: Dict[str, float] = {
    "oversized": 1.0, "relaxed": 0.5, "regular": 0.0,
    "straight": 0.0, "fitted": -0.5, "slim": -0.5,
}

USER_NOISE_LEVELS = [
    (0.70, 0.4),   # 70% consistent
    (0.20, 1.0),   # 20% moderately inconsistent
    (0.10, 2.0),   # 10% noisy
]

DATA_DIR = Path("data")
MODELS_DIR = Path("models")


# ---------------------------------------------------------------------------
# Data classes (simple dict-serialisable)
# ---------------------------------------------------------------------------

@dataclass
class SyntheticUser:
    user_id: str
    height_cm: float
    weight_kg: float
    preferred_top_fit: str
    preferred_bottom_fit: str
    noise_level: float           # personal inconsistency σ
    # True latent size (index into scale)
    true_top_size_idx: int
    true_bottom_size_idx: int
    body_attributes: Dict[str, str] = field(default_factory=lambda: {"build": "average"})


@dataclass
class SyntheticProduct:
    product_id: str
    brand_name: str
    brand_relative_fit: float
    brand_noise: float
    category: str
    silhouette_type: str
    available_sizes: List[str]
    scale: str   # "tops" | "bottoms"


@dataclass
class SyntheticInteraction:
    interaction_id: str
    user_id: str
    product_id: str
    candidate_size: str
    # Context
    category: str
    brand_name: str
    brand_relative_fit: float
    silhouette_type: str
    height_cm: float
    weight_kg: float
    preferred_fit: str   # for this category type
    # History snapshot at time of interaction
    closet_count: int
    category_closet_count: int
    category_mode_size_numeric: float
    category_size_entropy: float
    same_brand_item_count: int
    perfect_fit_count: int
    slightly_tight_count: int
    slightly_loose_count: int
    total_purchases: int
    category_purchases: int
    brand_purchases: int
    successful_fit_count: int
    return_count: int
    too_tight_count: int
    too_loose_count: int
    brand_too_tight_count: int
    brand_too_loose_count: int
    brand_fit_success_rate: float
    category_fit_success_rate: float
    user_fit_success_rate: float
    available_size_count: int
    candidate_size_numeric: float
    candidate_size_position: float
    candidate_size_delta_from_user_mode: float
    candidate_size_delta_from_brand_mode: float
    bmi: float
    preferred_fit_enc: int
    category_enc: int
    silhouette_enc: int
    structure_level_enc: int
    # Outcome
    target_fit: int              # 1 = perfect fit, 0 = not perfect
    raw_outcome: str             # "perfect" | "slightly_tight" | "slightly_loose" | "very_tight" | "very_loose"
    timestamp: str


# ---------------------------------------------------------------------------
# Encoding lookups  (must match feature_builder.py)
# ---------------------------------------------------------------------------

TOPS_ENC = {s: i for i, s in enumerate(TOPS_SCALE)}
BOTTOMS_ENC = {s: i for i, s in enumerate(BOTTOMS_SCALE)}

CATEGORY_ENC: Dict[str, int] = {
    "t-shirts": 0, "shirts": 1, "hoodies": 2, "sweaters": 3,
    "jackets": 4, "jeans": 5, "trousers": 6, "shorts": 7,
    "dresses": 8, "other": 9,
}

SILHOUETTE_ENC: Dict[str, int] = {
    "slim": 0, "regular": 1, "straight": 2,
    "relaxed": 3, "oversized": 4, "other": 5,
}

STRUCTURE_ENC: Dict[str, int] = {"structured": 0, "balanced": 1, "soft": 2}

TOP_FIT_ENC: Dict[str, int] = {
    "fitted": 0, "slim": 1, "regular": 2, "relaxed": 3, "oversized": 4,
}
BOTTOM_FIT_ENC: Dict[str, int] = {
    "slim": 0, "straight": 1, "regular": 2, "relaxed": 3, "wide": 4,
}


def _size_to_numeric(size: str, scale: List[str]) -> float:
    try:
        return float(scale.index(size))
    except ValueError:
        return -1.0


def _mode(lst: List[float]) -> float:
    if not lst:
        return -1.0
    counts: Dict[float, int] = {}
    for v in lst:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)


def _entropy(lst: List[float]) -> float:
    if not lst:
        return 0.0
    import math
    counts: Dict[float, int] = {}
    for v in lst:
        counts[v] = counts.get(v, 0) + 1
    total = len(lst)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _safe_rate(num: int, denom: int) -> float:
    return num / denom if denom > 0 else 0.0


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _generate_users(n: int, rng: np.random.Generator) -> List[SyntheticUser]:
    users = []
    # Noise level distribution
    cumulative = 0.0
    noise_breakpoints = []
    for frac, noise_val in USER_NOISE_LEVELS:
        cumulative += frac
        noise_breakpoints.append((cumulative, noise_val))

    for _ in range(n):
        # Assign noise tier
        r = rng.random()
        noise_level = USER_NOISE_LEVELS[-1][1]
        for threshold, nl in noise_breakpoints:
            if r < threshold:
                noise_level = nl
                break

        height_cm = float(rng.normal(175, 10))
        weight_kg = float(rng.normal(72, 14))
        height_cm = max(150.0, min(210.0, height_cm))
        weight_kg = max(40.0, min(140.0, weight_kg))

        pref_top = rng.choice(TOP_FIT_PREFS)
        pref_bot = rng.choice(BOTTOM_FIT_PREFS)

        # Latent true size — derived from BMI + height
        bmi = weight_kg / ((height_cm / 100.0) ** 2)
        # Map BMI to size index: BMI ~18 → XS (1), ~22 → S/M (2/3), ~26 → L (4), >30 → XL+ (5+)
        top_idx = int(max(0, min(len(TOPS_SCALE) - 1, (bmi - 16) * 0.4)))
        bot_idx = int(max(0, min(len(BOTTOMS_SCALE) - 1, (bmi - 16) * 0.5)))

        users.append(SyntheticUser(
            user_id=str(uuid.uuid4()),
            height_cm=height_cm,
            weight_kg=weight_kg,
            preferred_top_fit=pref_top,
            preferred_bottom_fit=pref_bot,
            noise_level=noise_level,
            true_top_size_idx=top_idx,
            true_bottom_size_idx=bot_idx,
        ))

    return users


def _generate_products(n: int, rng: np.random.Generator) -> List[SyntheticProduct]:
    products = []
    cat_names = list(CATEGORIES.keys())

    for _ in range(n):
        brand = rng.choice(BRAND_PROFILES)
        cat_name = rng.choice(cat_names)
        cat_info = CATEGORIES[cat_name]
        silhouette = rng.choice(cat_info["silhouettes"])

        scale = TOPS_SCALE if cat_info["scale"] == "tops" else BOTTOMS_SCALE
        # Pick a contiguous slice of 4–7 sizes to be "available"
        n_sizes = int(rng.integers(4, 8))
        start_idx = int(rng.integers(0, max(1, len(scale) - n_sizes)))
        available = scale[start_idx: start_idx + n_sizes]

        products.append(SyntheticProduct(
            product_id=str(uuid.uuid4()),
            brand_name=brand["name"],
            brand_relative_fit=brand["relative_fit"],
            brand_noise=brand["noise"],
            category=cat_name,
            silhouette_type=silhouette,
            available_sizes=available,
            scale=cat_info["scale"],
        ))

    return products


def _latent_fit_score(
    user: SyntheticUser,
    product: SyntheticProduct,
    candidate_size: str,
    rng: np.random.Generator,
) -> float:
    """
    Compute a latent fit score for (user, product, candidate_size).

    Conceptually:
        score = body_compatibility
              + candidate_size_alignment
              + brand_bias
              + silhouette_effect
              + preference_effect
              + noise

    Returns a float; sigmoid(score) → P(perfect_fit).
    """
    scale = TOPS_SCALE if product.scale == "tops" else BOTTOMS_SCALE
    true_idx = (
        user.true_top_size_idx if product.scale == "tops" else user.true_bottom_size_idx
    )
    cand_idx = _size_to_numeric(candidate_size, scale)

    # Brand bias shifts the user's effective size requirement
    brand_shifted_true = true_idx - product.brand_relative_fit  # runs small → user needs +1

    # Silhouette effect: oversized garments fit larger sizes, slim garments need to be bigger
    sil_offset = SILHOUETTE_OFFSET.get(product.silhouette_type, 0.0)
    effective_true = brand_shifted_true - sil_offset   # higher sil_offset → user should go up

    # Preference alignment: if user prefers relaxed and it's slim, they may want bigger
    pref = user.preferred_top_fit if product.scale == "tops" else user.preferred_bottom_fit
    pref_off = PREF_OFFSET.get(pref, 0.0)
    effective_true += pref_off

    # Alignment penalty: quadratic around effective_true
    alignment = -(cand_idx - effective_true) ** 2 * 1.2

    # Add brand noise
    brand_noise = float(rng.normal(0, product.brand_noise))

    # Add user noise (personal inconsistency)
    user_noise = float(rng.normal(0, user.noise_level))

    score = alignment + brand_noise + user_noise
    return score


def _score_to_outcome(prob: float, rng: np.random.Generator) -> Tuple[int, str]:
    """Convert P(perfect_fit) to a discrete outcome label."""
    r = float(rng.random())
    if r < prob:
        return 1, "perfect"
    # Distribute imperfect outcomes
    r2 = float(rng.random())
    if r2 < 0.35:
        return 0, "slightly_tight"
    elif r2 < 0.55:
        return 0, "slightly_loose"
    elif r2 < 0.75:
        return 0, "very_tight"
    else:
        return 0, "very_loose"


def _generate_interactions(
    users: List[SyntheticUser],
    products: List[SyntheticProduct],
    n_interactions: int,
    rng: np.random.Generator,
    start_date: datetime,
) -> List[SyntheticInteraction]:
    """
    Simulate a customer journey for each user.

    State is tracked per-user so that history features are computed from
    chronologically earlier events only (no leakage).
    """
    interactions: List[SyntheticInteraction] = []

    # Index products
    product_map = {p.product_id: p for p in products}
    product_list = products

    # Per-user state
    user_closet: Dict[str, List[Dict]] = {u.user_id: [] for u in users}
    user_purchases: Dict[str, List[Dict]] = {u.user_id: [] for u in users}
    user_feedback: Dict[str, List[Dict]] = {u.user_id: [] for u in users}

    current_time = start_date
    interactions_per_step = max(1, n_interactions // (len(users) * 3))

    total_generated = 0
    user_arr = list(users)

    while total_generated < n_interactions:
        user = rng.choice(user_arr)
        product = rng.choice(product_list)
        scale = TOPS_SCALE if product.scale == "tops" else BOTTOMS_SCALE

        # Pick candidate size to "recommend" (simulate recommender picking best available)
        # For training diversity: sometimes pick wrong size too (with lower probability)
        if float(rng.random()) < 0.7:
            # "Reasonable" pick — near user's true size
            true_idx = (
                user.true_top_size_idx if product.scale == "tops" else user.true_bottom_size_idx
            )
            # Clamp to available
            candidates = product.available_sizes
            numeric = [_size_to_numeric(s, scale) for s in candidates]
            closest = min(range(len(numeric)), key=lambda i: abs(numeric[i] - true_idx))
            # Sometimes shift by ±1 for training diversity
            shift = int(rng.choice([-1, 0, 0, 1]))
            idx = max(0, min(len(candidates) - 1, closest + shift))
            candidate_size = candidates[idx]
        else:
            candidate_size = rng.choice(product.available_sizes)

        # ── Compute history snapshot for this user ──────────────────────────
        uid = user.user_id
        closet = user_closet[uid]
        feedback_hist = user_feedback[uid]
        purchases = user_purchases[uid]

        cat_lower = product.category.lower()
        brand_lower = product.brand_name.lower()

        cat_closet = [c for c in closet if c["category"] == cat_lower]
        brand_closet = [c for c in closet if c["brand"] == brand_lower]
        cat_brand_closet = [c for c in cat_closet if c["brand"] == brand_lower]

        cat_sizes_numeric = [c["size_numeric"] for c in cat_closet]
        brand_sizes_numeric = [c["size_numeric"] for c in brand_closet]

        cat_mode_numeric = _mode(cat_sizes_numeric) if cat_sizes_numeric else -1.0
        brand_mode_numeric = _mode(brand_sizes_numeric) if brand_sizes_numeric else -1.0
        cand_numeric = _size_to_numeric(candidate_size, scale)
        scale_len = len(scale) - 1
        cand_position = cand_numeric / scale_len if scale_len > 0 else 0.5

        delta_user = (cand_numeric - cat_mode_numeric) if cat_mode_numeric >= 0 else 0.0
        delta_brand = (cand_numeric - brand_mode_numeric) if brand_mode_numeric >= 0 else 0.0

        perfect_fit_count = sum(1 for c in cat_closet if c.get("fit_rating") == "perfect")
        slightly_tight_count = sum(1 for c in cat_closet if c.get("fit_rating") == "a_little_tight")
        slightly_loose_count = sum(1 for c in cat_closet if c.get("fit_rating") == "a_little_loose")

        total_purchases = len(feedback_hist)
        cat_fb = [f for f in feedback_hist if f["category"] == cat_lower]
        brand_fb = [f for f in feedback_hist if f["brand"] == brand_lower]

        successful = sum(1 for f in feedback_hist if f["outcome"] == "kept")
        returned = sum(1 for f in feedback_hist if f["outcome"] == "returned")
        too_tight_count = sum(1 for f in feedback_hist if f.get("reason") == "too_tight")
        too_loose_count = sum(1 for f in feedback_hist if f.get("reason") == "too_loose")
        brand_too_tight = sum(1 for f in brand_fb if f.get("reason") == "too_tight")
        brand_too_loose = sum(1 for f in brand_fb if f.get("reason") == "too_loose")
        brand_success = sum(1 for f in brand_fb if f["outcome"] == "kept")
        cat_success = sum(1 for f in cat_fb if f["outcome"] == "kept")

        bmi = user.weight_kg / ((user.height_cm / 100.0) ** 2)
        bmi = max(10.0, min(60.0, bmi))

        pref = (
            user.preferred_bottom_fit if product.scale == "bottoms" else user.preferred_top_fit
        )
        pref_enc = (
            BOTTOM_FIT_ENC.get(pref, 2) if product.scale == "bottoms"
            else TOP_FIT_ENC.get(pref, 2)
        )

        # ── Generate fit outcome ─────────────────────────────────────────────
        raw_score = _latent_fit_score(user, product, candidate_size, rng)
        fit_prob = _sigmoid(raw_score)
        target, raw_outcome = _score_to_outcome(fit_prob, rng)

        # ── Update user state ────────────────────────────────────────────────
        fit_label = "perfect" if target == 1 else (
            "a_little_tight" if "tight" in raw_outcome else "a_little_loose"
        )
        user_closet[uid].append({
            "category": cat_lower,
            "brand": brand_lower,
            "size_numeric": cand_numeric,
            "size_label": candidate_size,
            "fit_rating": fit_label,
        })
        outcome = "kept" if target == 1 else "returned"
        reason = None if target == 1 else ("too_tight" if "tight" in raw_outcome else "too_loose")
        user_feedback[uid].append({
            "category": cat_lower,
            "brand": brand_lower,
            "outcome": outcome,
            "reason": reason,
        })

        current_time += timedelta(hours=float(rng.integers(1, 72)))

        interactions.append(SyntheticInteraction(
            interaction_id=str(uuid.uuid4()),
            user_id=uid,
            product_id=product.product_id,
            candidate_size=candidate_size,
            category=cat_lower,
            brand_name=brand_lower,
            brand_relative_fit=product.brand_relative_fit,
            silhouette_type=product.silhouette_type,
            height_cm=user.height_cm,
            weight_kg=user.weight_kg,
            preferred_fit=pref,
            closet_count=len(closet),
            category_closet_count=len(cat_closet),
            category_mode_size_numeric=cat_mode_numeric,
            category_size_entropy=_entropy(cat_sizes_numeric),
            same_brand_item_count=len(brand_closet),
            perfect_fit_count=perfect_fit_count,
            slightly_tight_count=slightly_tight_count,
            slightly_loose_count=slightly_loose_count,
            total_purchases=total_purchases,
            category_purchases=len(cat_fb),
            brand_purchases=len(brand_fb),
            successful_fit_count=successful,
            return_count=returned,
            too_tight_count=too_tight_count,
            too_loose_count=too_loose_count,
            brand_too_tight_count=brand_too_tight,
            brand_too_loose_count=brand_too_loose,
            brand_fit_success_rate=_safe_rate(brand_success, len(brand_fb)),
            category_fit_success_rate=_safe_rate(cat_success, len(cat_fb)),
            user_fit_success_rate=_safe_rate(successful, total_purchases),
            available_size_count=len(product.available_sizes),
            candidate_size_numeric=cand_numeric,
            candidate_size_position=cand_position,
            candidate_size_delta_from_user_mode=delta_user,
            candidate_size_delta_from_brand_mode=delta_brand,
            bmi=bmi,
            preferred_fit_enc=pref_enc,
            category_enc=CATEGORY_ENC.get(cat_lower, 9),
            silhouette_enc=SILHOUETTE_ENC.get(product.silhouette_type, 5),
            structure_level_enc=1,   # balanced default in synthetic
            target_fit=target,
            raw_outcome=raw_outcome,
            timestamp=current_time.isoformat(),
        ))

        total_generated += 1

    return interactions


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_dataset(df: pd.DataFrame) -> None:
    print("\n── Dataset Validation ──────────────────────────────────────────")
    print(f"  Total rows        : {len(df):,}")
    print(f"  Perfect fit rate  : {df['target_fit'].mean():.2%}  (target: 30–60%)")
    print(f"  Category dist:\n{df['category'].value_counts().to_string()}")
    print(f"  Brand dist sample:\n{df['brand_name'].value_counts().head(5).to_string()}")
    print(f"  Silhouette dist:\n{df['silhouette_type'].value_counts().to_string()}")

    fit_rate = df["target_fit"].mean()
    if fit_rate > 0.75:
        print("  ⚠  WARNING: Perfect fit rate > 75% — data may be unrealistically positive.")
    if fit_rate < 0.20:
        print("  ⚠  WARNING: Perfect fit rate < 20% — data may be too skewed negative.")
    print("────────────────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate(
    n_users: int = 3_000,
    n_products: int = 500,
    n_interactions: int = 20_000,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    print(f"Generating {n_users:,} users...")
    users = _generate_users(n_users, rng)

    print(f"Generating {n_products:,} products...")
    products = _generate_products(n_products, rng)

    print(f"Simulating {n_interactions:,} interactions (this may take ~30s)...")
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    interactions = _generate_interactions(users, products, n_interactions, rng, start_date)

    # Serialise
    users_df = pd.DataFrame([u.__dict__ for u in users])
    products_df = pd.DataFrame([p.__dict__ for p in products])
    interactions_df = pd.DataFrame([i.__dict__ for i in interactions])

    return users_df, products_df, interactions_df


def main():
    DATA_DIR.mkdir(exist_ok=True)
    MODELS_DIR.mkdir(exist_ok=True)

    users_df, products_df, interactions_df = generate()

    # Save raw tables
    users_df.to_parquet(DATA_DIR / "synthetic_users.parquet", index=False)
    products_df.to_parquet(DATA_DIR / "synthetic_products.parquet", index=False)
    interactions_df.to_parquet(DATA_DIR / "synthetic_interactions.parquet", index=False)

    # Build training dataset — interactions are the primary training table
    from ml.schemas import FEATURE_COLUMNS
    feature_cols = FEATURE_COLUMNS
    available_cols = [c for c in feature_cols if c in interactions_df.columns]
    missing_cols = [c for c in feature_cols if c not in interactions_df.columns]
    if missing_cols:
        print(f"  Note: missing feature columns (will be zero-filled): {missing_cols}")
        for col in missing_cols:
            interactions_df[col] = 0.0

    training_df = interactions_df[available_cols + ["target_fit", "timestamp"]].copy()
    training_df.to_parquet(DATA_DIR / "training_dataset.parquet", index=False)

    validate_dataset(interactions_df)

    print("✓ Saved:")
    print(f"  {DATA_DIR}/synthetic_users.parquet        ({len(users_df):,} rows)")
    print(f"  {DATA_DIR}/synthetic_products.parquet     ({len(products_df):,} rows)")
    print(f"  {DATA_DIR}/synthetic_interactions.parquet ({len(interactions_df):,} rows)")
    print(f"  {DATA_DIR}/training_dataset.parquet       ({len(training_df):,} rows)")


if __name__ == "__main__":
    main()
