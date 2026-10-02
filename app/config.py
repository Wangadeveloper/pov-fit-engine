import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROJECT_NAME = "POV — Fit Intelligence Platform"
    SECRET_KEY = os.environ.get("JWT_SECRET", "supersecret_change_me_in_production")
    
    # Use standard sqlite driver, not aiosqlite
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///../pov.db")
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite+aiosqlite"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("sqlite+aiosqlite", "sqlite")
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    
    YOUCAM_API_KEY = os.environ.get("YOUCAM_API_KEY", "sk-YPdtdij2CGLKt4VuoOiyY3DzgjNgOjtex5NmcY4iMBnxCSa4f9vzGeG_Yck1vEOn")
    YOUCAM_API_BASE_URL = os.environ.get("YOUCAM_API_BASE_URL", "https://yce-api-01.makeupar.com/s2s")
