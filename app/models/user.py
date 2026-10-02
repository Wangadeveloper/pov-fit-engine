import uuid
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime
from app.extensions import db

class User(db.Model, UserMixin):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    fit_profile: Mapped["FitProfile"] = relationship("FitProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    closet_items: Mapped[list["ClosetItem"]] = relationship("ClosetItem", back_populates="user", cascade="all, delete-orphan")
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")
    feedbacks: Mapped[list["FitFeedback"]] = relationship("FitFeedback", back_populates="user", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    recommendation_events: Mapped[list["RecommendationEvent"]] = relationship("RecommendationEvent", back_populates="user", cascade="all, delete-orphan")
