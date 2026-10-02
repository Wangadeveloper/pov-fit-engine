import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, Float, JSON
from app.extensions import db

class FitProfile(db.Model):
    __tablename__ = "fit_profiles"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    
    preferred_top_fit: Mapped[str] = mapped_column(String(50), default="regular")
    preferred_bottom_fit: Mapped[str] = mapped_column(String(50), default="straight")
    preferred_jacket_fit: Mapped[str] = mapped_column(String(50), default="regular")
    comfort_preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    try_on_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    confidence: Mapped[float] = mapped_column(Float, default=0.25)
    profile_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    calibration_level: Mapped[str] = mapped_column(String(50), default="low")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship("User", back_populates="fit_profile")
    attributes: Mapped[list["FitAttribute"]] = relationship("FitAttribute", back_populates="fit_profile", cascade="all, delete-orphan")


class FitAttribute(db.Model):
    __tablename__ = "fit_attributes"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fit_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fit_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    attribute_key: Mapped[str] = mapped_column(String(50), nullable=False)
    attribute_value: Mapped[str] = mapped_column(String(50), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    fit_profile: Mapped["FitProfile"] = relationship("FitProfile", back_populates="attributes")
