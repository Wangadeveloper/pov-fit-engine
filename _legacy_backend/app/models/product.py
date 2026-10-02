import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, Float, TEXT
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # T-Shirts | Shirts | Hoodies | Sweaters | Jackets | Jeans | Trousers | Shorts | Dresses
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    silhouette_type: Mapped[str] = mapped_column(String(50), default="regular")  # slim, regular, relaxed, oversized
    structure_level: Mapped[str] = mapped_column(String(50), default="balanced")  # structured, balanced, soft
    color_family: Mapped[str] = mapped_column(String(50), default="neutral")  # neutral, bold, dark, light
    visual_density: Mapped[str] = mapped_column(String(50), default="minimal")  # minimal, detailed
    fabric_drape: Mapped[str | None] = mapped_column(String(50), nullable=True)  # stiff, fluid, heavy
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    brand: Mapped["Brand"] = relationship("Brand", back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship("Recommendation", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    
    size_label: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fabric: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stretch: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 rigid, 1.0 highly stretchy
    
    chest_ease: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist_ease: Mapped[float | None] = mapped_column(Float, nullable=True)
    inseam: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleeve_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    shoulder_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="variant", cascade="all, delete-orphan")
