"""
Evaluation script for POV Recommendation Engines.

Compares Rule Engine, LightGBM Engine, and Hybrid Engine on synthetic test set.
Also runs a personalization effect demonstration.

Usage::

    python -m ml.evaluate
"""

import json
import os
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score, log_loss, brier_score_loss

from app.recommendation.base import UserHistory
from app.recommendation.rule_engine import RuleBasedRecommendationEngine
from app.recommendation.ml_engine import MLRecommendationEngine
from app.recommendation.hybrid_engine import HybridRecommendationEngine
from app.models.user import User
from app.models.fit_profile import FitProfile


def load_test_data(data_dir="data"):
    interactions_path = os.path.join(data_dir, "synthetic_interactions.parquet")
    users_path = os.path.join(data_dir, "synthetic_users.parquet")
    products_path = os.path.join(data_dir, "synthetic_products.parquet")

    if not (os.path.exists(interactions_path) and os.path.exists(users_path) and os.path.exists(products_path)):
        print("Data files missing. Please run `python -m ml.synthetic_data` first.")
        return None, None, None

    interactions_df = pd.read_parquet(interactions_path)
    users_df = pd.read_parquet(users_path)
    products_df = pd.read_parquet(products_path)

    # Use test split (last 15% of interactions by timestamp)
    interactions_df = interactions_df.sort_values("timestamp")
    test_cutoff = int(len(interactions_df) * 0.85)
    test_df = interactions_df.iloc[test_cutoff:]

    return test_df, users_df, products_df


def evaluate_engines():
    test_df, users_df, products_df = load_test_data()
    if test_df is None:
        return

    rule_engine = RuleBasedRecommendationEngine()
    ml_engine = MLRecommendationEngine(model_path="models/pov_fit_model.txt")
    hybrid_engine = HybridRecommendationEngine(ml_engine=ml_engine, rule_engine=rule_engine, min_confidence=0.55)

    print(f"Evaluating {len(test_df)} test interactions across Rule, ML, and Hybrid engines...")

    user_map = users_df.set_index("user_id").to_dict(orient="index")
    product_map = products_df.set_index("product_id").to_dict(orient="index")

    # Limit to sample for fast evaluation if large
    eval_sample = test_df.sample(n=min(500, len(test_df)), random_state=42)

    results = {
        "Rule Engine": {"top1_correct": 0, "top2_correct": 0, "total": 0, "y_true": [], "y_prob": []},
        "ML Engine": {"top1_correct": 0, "top2_correct": 0, "total": 0, "y_true": [], "y_prob": []},
        "Hybrid Engine": {"top1_correct": 0, "top2_correct": 0, "total": 0, "y_true": [], "y_prob": []},
    }

    engines = [
        ("Rule Engine", rule_engine),
        ("ML Engine", ml_engine),
        ("Hybrid Engine", hybrid_engine)
    ]

    for idx, row in eval_sample.iterrows():
        u_data = user_map.get(row["user_id"])
        p_data = product_map.get(row["product_id"])

        if not u_data or not p_data:
            continue

        profile = FitProfile(
            height_cm=u_data["height_cm"],
            weight_kg=u_data["weight_kg"],
            preferred_top_fit=u_data.get("preferred_top_fit", "regular"),
            preferred_bottom_fit=u_data.get("preferred_bottom_fit", "straight"),
        )

        user_history = UserHistory(profile=profile, closet=[], feedback=[])

        product = {
            "category": p_data["category"],
            "silhouette": p_data.get("silhouette_type", p_data.get("silhouette", "regular")),
            "brand": p_data.get("brand_name", p_data.get("brand", "")),
            "brand_relative_fit": p_data.get("brand_relative_fit", 0.0),
            "available_sizes": list(p_data["available_sizes"]) if hasattr(p_data["available_sizes"], "__iter__") else ["S", "M", "L", "XL"]
        }

        true_size = row.get("candidate_size", row.get("chosen_size", "M"))
        is_perfect = row.get("target_fit", 0) == 1 or row.get("raw_outcome", "") == "perfect"

        for name, engine in engines:
            res = engine.recommend(user_history=user_history, product=product)
            rec_size = res.get("recommended_size")
            scores = res.get("all_scores", {})
            conf = res.get("fit_probability", 0.5)

            # Top-1 accuracy check
            if rec_size == true_size:
                results[name]["top1_correct"] += 1

            # Top-2 accuracy check
            sorted_sizes = sorted(scores.keys(), key=lambda s: scores[s], reverse=True)
            if true_size in sorted_sizes[:2]:
                results[name]["top2_correct"] += 1

            results[name]["total"] += 1
            results[name]["y_true"].append(1 if is_perfect else 0)
            results[name]["y_prob"].append(conf if rec_size == true_size else 1.0 - conf)

    print("\n" + "="*65)
    print(f"{'Engine':<18} | {'Top-1 Acc':<10} | {'Top-2 Acc':<10} | {'ROC-AUC':<9} | {'Log Loss':<9}")
    print("="*65)

    report_md = "# POV Recommendation Engine Evaluation Report\n\n"
    report_md += "| Engine | Top-1 Acc | Top-2 Acc | ROC-AUC | PR-AUC | Log Loss | Brier Score |\n"
    report_md += "|---|---|---|---|---|---|---|\n"

    for name in ["Rule Engine", "ML Engine", "Hybrid Engine"]:
        r = results[name]
        tot = r["total"] if r["total"] > 0 else 1
        t1_acc = r["top1_correct"] / tot
        t2_acc = r["top2_correct"] / tot

        y_t = np.array(r["y_true"])
        y_p = np.clip(np.array(r["y_prob"]), 1e-15, 1 - 1e-15)

        try:
            auc = roc_auc_score(y_t, y_p)
            pr_auc = average_precision_score(y_t, y_p)
            loss = log_loss(y_t, y_p)
            brier = brier_score_loss(y_t, y_p)
            auc_str, pr_str, loss_str, brier_str = f"{auc:.4f}", f"{pr_auc:.4f}", f"{loss:.4f}", f"{brier:.4f}"
        except Exception:
            auc_str, pr_str, loss_str, brier_str = "N/A", "N/A", "N/A", "N/A"

        print(f"{name:<18} | {t1_acc*100:6.2f}%    | {t2_acc*100:6.2f}%    | {auc_str:<9} | {loss_str:<9}")
        report_md += f"| {name} | {t1_acc*100:.2f}% | {t2_acc*100:.2f}% | {auc_str} | {pr_str} | {loss_str} | {brier_str} |\n"

    print("="*65 + "\n")
    return report_md


def demo_personalization_effect():
    print("--- Personalization Effect Demonstration ---")
    rule_engine = RuleBasedRecommendationEngine()
    ml_engine = MLRecommendationEngine(model_path="models/pov_fit_model.txt")
    hybrid_engine = HybridRecommendationEngine(ml_engine=ml_engine, rule_engine=rule_engine)

    profile = FitProfile(height_cm=175, weight_kg=72, preferred_top_fit="fitted", preferred_bottom_fit="straight")

    product = {
        "category": "Tops",
        "silhouette": "regular",
        "brand": "BrandX",
        "brand_relative_fit": 0.0,
        "available_sizes": ["S", "M", "L", "XL"]
    }

    # Step 1: Initial cold start recommendation
    h0 = UserHistory(profile=profile, closet=[], feedback=[])
    res0 = hybrid_engine.recommend(user_history=h0, product=product)

    print(f"Cold Start Recommendation: {res0['recommended_size']} (source: {res0.get('recommendation_source')}, conf: {res0.get('fit_probability', 0):.2f})")

    # Step 2: Add feedback: bought M -> too_tight, bought L -> perfect, bought L -> perfect
    feedback_history = [
        {"product_id": "p1", "category": "Tops", "brand": "BrandX", "size": "M", "outcome": "too_tight"},
        {"product_id": "p2", "category": "Tops", "brand": "BrandX", "size": "L", "outcome": "perfect"},
        {"product_id": "p3", "category": "Tops", "brand": "BrandY", "size": "L", "outcome": "perfect"},
    ]

    h1 = UserHistory(profile=profile, closet=[], feedback=feedback_history)
    res1 = hybrid_engine.recommend(user_history=h1, product=product)

    print(f"Post-Feedback Recommendation: {res1['recommended_size']} (source: {res1.get('recommendation_source')}, conf: {res1.get('fit_probability', 0):.2f})")
    print(f"Score Distribution: {res1.get('all_scores')}")
    print("-------------------------------------------\n")


if __name__ == "__main__":
    evaluate_engines()
    demo_personalization_effect()
