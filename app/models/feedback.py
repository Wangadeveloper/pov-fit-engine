import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, Boolean, JSON
from app.extensions import db

class FitFeedback(db.Model):
    __tablename__ = "fit_feedbacks"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    outcome_label: Mapped[str] = mapped_column(String(50), nullable=False)  # kept | returned | exchanged
    reason_label: Mapped[str | None] = mapped_column(String(100), nullable=True)  # too_tight, too_loose, didnt_like_fit, didnt_like_style, fabric_discomfort, other
    tight_loose_regions: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g., {"waist": "too_tight"}
    would_buy_again: Mapped[bool] = mapped_column(Boolean, default=True)
    final_size_worn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship("User", back_populates="feedbacks")
    purchase: Mapped["Purchase"] = relationship("Purchase", back_populates="feedback")
