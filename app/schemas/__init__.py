from app.schemas.user import UserCreate, UserLogin, UserOut, Token, TokenData
from app.schemas.fit import FitProfileSchema, FitProfileUpdate, OnboardingDetails, FitAttributeSchema
from app.schemas.closet import ClosetItemCreate, ClosetItemUpdate, ClosetItemSchema
from app.schemas.product import BrandSchema, ProductVariantSchema, ProductSchema, ProductDetailsSchema
from app.schemas.purchase import PurchaseCreate, PurchaseSchema
from app.schemas.feedback import FitFeedbackCreate, FitFeedbackSchema
from app.schemas.recommendation import RecommendationSchema, RecommendationResponse, RecommendationEventCreate

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserOut",
    "Token",
    "TokenData",
    "FitProfileSchema",
    "FitProfileUpdate",
    "OnboardingDetails",
    "FitAttributeSchema",
    "ClosetItemCreate",
    "ClosetItemUpdate",
    "ClosetItemSchema",
    "BrandSchema",
    "ProductVariantSchema",
    "ProductSchema",
    "ProductDetailsSchema",
    "PurchaseCreate",
    "PurchaseSchema",
    "FitFeedbackCreate",
    "FitFeedbackSchema",
    "RecommendationSchema",
    "RecommendationResponse",
    "RecommendationEventCreate",
]
