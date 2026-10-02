from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base

# Import all models so SQLAlchemy knows about them
from app.models import (  # noqa: F401
    User, FitProfile, FitAttribute, ClosetItem,
    Brand, Product, ProductVariant, Purchase,
    FitFeedback, Recommendation, RecommendationEvent,
)

from app.api import auth, users, fit, closet, products, recommendations, feedback, purchases, analytics, vto


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(fit.router, prefix=f"{settings.API_V1_STR}/fit", tags=["fit"])
app.include_router(closet.router, prefix=f"{settings.API_V1_STR}/closet", tags=["closet"])
app.include_router(products.router, prefix=f"{settings.API_V1_STR}/products", tags=["products"])
app.include_router(recommendations.router, prefix=f"{settings.API_V1_STR}/recommendations", tags=["recommendations"])
app.include_router(feedback.router, prefix=f"{settings.API_V1_STR}/feedback", tags=["feedback"])
app.include_router(purchases.router, prefix=f"{settings.API_V1_STR}/purchases", tags=["purchases"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(vto.router, prefix=f"{settings.API_V1_STR}/vto", tags=["vto"])


@app.get("/")
async def root():
    return {"message": "POV Fit Intelligence Platform API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
