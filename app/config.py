import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROJECT_NAME = "POV — Fit Intelligence Platform"
    SECRET_KEY = os.environ.get("JWT_SECRET", "supersecret_change_me_in_production")
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///pov.db")
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite+aiosqlite"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("sqlite+aiosqlite", "sqlite")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    
    YOUCAM_API_KEY = os.environ.get("YOUCAM_API_KEY", "sk-YPdtdij2CGLKt4VuoOiyY3DzgjNgOjtex5NmcY4iMBnxCSa4f9vzGeG_Yck1vEOn")
    YOUCAM_API_BASE_URL = os.environ.get("YOUCAM_API_BASE_URL", "https://yce-api-01.makeupar.com/s2s")

    # ── Qloo Cultural Intelligence API ────────────────────────────────────
    QLOO_API_KEY = os.environ.get("QLOO_API_KEY", "")
    QLOO_API_BASE_URL = os.environ.get("QLOO_API_BASE_URL", "https://api.qloo.com").rstrip("/")
    QLOO_SANDBOX_MODE = os.environ.get("QLOO_SANDBOX_MODE", "true").lower() in ("true", "1", "yes")

    # ── Recommendation engine ─────────────────────────────────────────────
    # Options: "hybrid" (default) | "ml" | "rule"
    RECOMMENDATION_ENGINE = os.environ.get("RECOMMENDATION_ENGINE", "hybrid")
    # Path to trained LightGBM model file (relative to project root)
    ML_MODEL_PATH = os.environ.get("ML_MODEL_PATH", "models/pov_fit_model.txt")
    # Minimum ML confidence to use ML result; below this falls back to rules
    ML_MIN_CONFIDENCE = float(os.environ.get("ML_MIN_CONFIDENCE", "0.55"))
    # Percentage of requests routed to ML/hybrid (0–100). 100 = all users.
    ML_ROLLOUT_PERCENTAGE = int(os.environ.get("ML_ROLLOUT_PERCENTAGE", "100"))

    # ── Gemini Agentic Intelligence Layer ─────────────────────────────────────
    # Set GEMINI_AGENT_ENABLED=false to bypass Gemini entirely (deterministic-only mode)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_AGENT_ENABLED = os.environ.get("GEMINI_AGENT_ENABLED", "true").lower() in ("true", "1", "yes")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "15"))
    # Max retries on transient errors only — quota errors skip retry immediately
    GEMINI_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "1"))
