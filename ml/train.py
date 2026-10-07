"""
LightGBM training script.

Usage::

    python -m ml.train [--data data/training_dataset.parquet] [--output models/]

Trains a binary classifier for P(perfect_fit), performs temporal train/val/test
split, runs Platt calibration on the validation set, and saves the model + metadata.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
MODELS_DIR = Path("models")

MODEL_NAME = "pov-fit-lgbm-v1"


def _temporal_split(df: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15):
    """Split by timestamp to simulate production (no future leakage)."""
    df = df.sort_values("timestamp").reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def _platt_fit(model, X_val: np.ndarray, y_val: np.ndarray):
    """Fit Platt scaling on the validation set."""
    raw_probs = model.predict(X_val)
    if raw_probs.ndim == 2:
        raw_probs = raw_probs[:, 1]
    # Fit logistic regression on logit of raw probabilities
    eps = 1e-7
    raw_probs = np.clip(raw_probs, eps, 1 - eps)
    logits = np.log(raw_probs / (1 - raw_probs)).reshape(-1, 1)
    lr = LogisticRegression(C=1e6, solver="lbfgs")
    lr.fit(logits, y_val)
    a = float(lr.coef_[0][0])
    b = float(lr.intercept_[0])
    logger.info("Platt calibration: a=%.4f, b=%.4f", a, b)
    return a, b


def _evaluate(model, X: np.ndarray, y: np.ndarray, name: str, platt_a: float = 1.0, platt_b: float = 0.0) -> dict:
    raw_probs = model.predict(X)
    if raw_probs.ndim == 2:
        raw_probs = raw_probs[:, 1]

    def platt(p):
        p = np.clip(p, 1e-7, 1 - 1e-7)
        logit = np.log(p / (1 - p))
        return 1.0 / (1.0 + np.exp(platt_a * logit + platt_b))

    cal_probs = platt(raw_probs)
    preds = (raw_probs >= 0.5).astype(int)

    metrics = {
        "roc_auc": round(float(roc_auc_score(y, raw_probs)), 4),
        "pr_auc": round(float(average_precision_score(y, raw_probs)), 4),
        "log_loss": round(float(log_loss(y, raw_probs)), 4),
        "brier_score": round(float(brier_score_loss(y, cal_probs)), 4),
        "accuracy": round(float((preds == y).mean()), 4),
    }
    logger.info("[%s] ROC-AUC=%.4f PR-AUC=%.4f LogLoss=%.4f Brier=%.4f Acc=%.4f",
                name, metrics["roc_auc"], metrics["pr_auc"],
                metrics["log_loss"], metrics["brier_score"], metrics["accuracy"])
    return metrics


def train(
    data_path: str = "data/training_dataset.parquet",
    output_dir: str = "models",
    model_version: str = MODEL_NAME,
):
    try:
        import lightgbm as lgb
    except ImportError:
        logger.error("lightgbm is not installed. Run: pip install lightgbm")
        sys.exit(1)

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # ── Load data ────────────────────────────────────────────────────────────
    logger.info("Loading training data from %s", data_path)
    df = pd.read_parquet(data_path)
    logger.info("Dataset: %d rows, %.1f%% perfect fit", len(df), df["target_fit"].mean() * 100)

    from ml.schemas import FEATURE_COLUMNS
    feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        logger.warning("Missing feature columns (zero-filled): %s", missing)
        for col in missing:
            df[col] = 0.0
        feature_cols = FEATURE_COLUMNS

    # ── Split ────────────────────────────────────────────────────────────────
    train_df, val_df, test_df = _temporal_split(df)
    logger.info("Split: train=%d val=%d test=%d", len(train_df), len(val_df), len(test_df))

    X_train = train_df[feature_cols].values.astype(np.float32)
    y_train = train_df["target_fit"].values.astype(int)
    X_val = val_df[feature_cols].values.astype(np.float32)
    y_val = val_df["target_fit"].values.astype(int)
    X_test = test_df[feature_cols].values.astype(np.float32)
    y_test = test_df["target_fit"].values.astype(int)

    # ── Train ────────────────────────────────────────────────────────────────
    logger.info("Training LightGBM...")
    dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    params = {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "learning_rate": 0.05,
        "num_leaves": 63,
        "max_depth": -1,
        "min_child_samples": 30,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
        "n_jobs": -1,
    }

    callbacks = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)]
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=1000,
        valid_sets=[dtrain, dval],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    # ── Platt calibration ─────────────────────────────────────────────────────
    platt_a, platt_b = _platt_fit(booster, X_val, y_val)

    # ── Evaluate ─────────────────────────────────────────────────────────────
    val_metrics = _evaluate(booster, X_val, y_val, "val", platt_a, platt_b)
    test_metrics = _evaluate(booster, X_test, y_test, "test", platt_a, platt_b)

    # ── Save model ───────────────────────────────────────────────────────────
    model_path = output_dir / "pov_fit_model.txt"
    booster.save_model(str(model_path))
    logger.info("Model saved to %s", model_path)

    # ── Save metadata ─────────────────────────────────────────────────────────
    meta = {
        "model_version": model_version,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "algorithm": "LightGBM",
        "features_version": "features-v1",
        "features": feature_cols,
        "n_estimators": booster.num_trees(),
        "calibration": {"a": platt_a, "b": platt_b},
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "split": {
            "train_rows": len(train_df),
            "val_rows": len(val_df),
            "test_rows": len(test_df),
        },
        "class_balance": {
            "train_positive_rate": float(y_train.mean()),
            "val_positive_rate": float(y_val.mean()),
            "test_positive_rate": float(y_test.mean()),
        },
    }
    meta_path = output_dir / "pov_fit_model.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Metadata saved to %s", meta_path)

    return booster, meta


def main():
    parser = argparse.ArgumentParser(description="Train POV fit recommendation model")
    parser.add_argument("--data", default="data/training_dataset.parquet")
    parser.add_argument("--output", default="models")
    parser.add_argument("--version", default=MODEL_NAME)
    args = parser.parse_args()

    booster, meta = train(
        data_path=args.data,
        output_dir=args.output,
        model_version=args.version,
    )
    print(f"\n✓ Training complete.")
    print(f"  Model version  : {meta['model_version']}")
    print(f"  Estimators     : {meta['n_estimators']}")
    print(f"  Val  ROC-AUC   : {meta['val_metrics']['roc_auc']}")
    print(f"  Test ROC-AUC   : {meta['test_metrics']['roc_auc']}")
    print(f"  Model file     : models/pov_fit_model.txt")


if __name__ == "__main__":
    main()
