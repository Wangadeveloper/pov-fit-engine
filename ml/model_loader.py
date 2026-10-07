"""
Model loader — singleton with lazy initialisation.

Loads the LightGBM model once on first access and caches it in memory.
Returns None when the model file is not found — the hybrid engine
interprets this as a signal to fall back to the rule engine.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)

_model_cache: Optional[Any] = None
_meta_cache: Optional[dict] = None
_lock = Lock()


def _resolve_path(path_str: str) -> Path:
    """Resolve relative paths against the project root (CWD)."""
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(os.getcwd()) / p
    return p


def load_model(model_path: str) -> Optional[Any]:
    """
    Load the LightGBM model from *model_path* (thread-safe, cached).

    Returns the loaded booster, or None if the file does not exist.
    """
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    with _lock:
        if _model_cache is not None:   # double-checked locking
            return _model_cache
        try:
            import lightgbm as lgb  # noqa: PLC0415
        except ImportError:
            logger.error("lightgbm is not installed. ML engine unavailable.")
            return None

        resolved = _resolve_path(model_path)
        if not resolved.exists():
            logger.warning("ML model not found at %s. ML engine will be unavailable.", resolved)
            return None

        try:
            model = lgb.Booster(model_file=str(resolved))
            _model_cache = model
            logger.info("LightGBM model loaded from %s", resolved)
            return model
        except Exception as exc:
            logger.error("Failed to load LightGBM model: %s", exc)
            return None


def load_meta(model_path: str) -> dict:
    """Load accompanying model metadata JSON, if present."""
    global _meta_cache
    if _meta_cache is not None:
        return _meta_cache

    meta_path = _resolve_path(model_path).with_suffix(".json")
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                _meta_cache = json.load(f)
            return _meta_cache
        except Exception:
            pass
    return {}


def clear_cache() -> None:
    """Clear cached model (useful for testing)."""
    global _model_cache, _meta_cache
    with _lock:
        _model_cache = None
        _meta_cache = None
