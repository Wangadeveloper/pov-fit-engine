import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, Float, JSON
from app.extensions import db

class Recommendation(db.Model):
    __tablename__ = "recommendations"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    
    recommended_size: Mapped[str] = mapped_column(String(20), nullable=False)
    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    fit_prediction: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship("User", back_populates="recommendations")
    product: Mapped["Product"] = relationship("Product", back_populates="recommendations")
    events: Mapped[list["RecommendationEvent"]] = relationship("RecommendationEvent", back_populates="recommendation", cascade="all, delete-orphan")


class RecommendationEvent(db.Model):
    __tablename__ = "recommendation_events"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # viewed | clicked | size_viewed | added_to_closet | purchased | feedback_submitted | returned
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship("User", back_populates="recommendation_events")
    recommendation: Mapped["Recommendation"] = relationship("Recommendation", back_populates="events")
