import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Float
from app.extensions import db

class Brand(db.Model):
    __tablename__ = "brands"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    relative_fit: Mapped[float] = mapped_column(Float, default=0.0)  # -1.0 runs small, +1.0 runs large, 0.0 standard
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    products: Mapped[list["Product"]] = relationship("Product", back_populates="brand", cascade="all, delete-orphan")
