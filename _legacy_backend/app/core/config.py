from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "POV — Fit Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    JWT_SECRET: str = "supersecret_change_me_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    DATABASE_URL: str = "sqlite+aiosqlite:///./pov.db"
    
    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    
    # YouCam API Configuration
    YOUCAM_API_KEY: str = "sk-YPdtdij2CGLKt4VuoOiyY3DzgjNgOjtex5NmcY4iMBnxCSa4f9vzGeG_Yck1vEOn"
    YOUCAM_API_BASE_URL: str = "https://yce-api-01.makeupar.com/s2s"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
