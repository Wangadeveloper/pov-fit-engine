import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.core.database import Base
from app.models.brand import Brand
from app.models.product import Product, ProductVariant
from sqlalchemy.future import select

# We reuse the settings and engine
engine = create_async_engine(settings.DATABASE_URL)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)

BRANDS_DATA = [
    {"name": "Nike", "relative_fit": -0.2},      # Runs slightly small
    {"name": "Zara", "relative_fit": -0.6},      # Runs small (needs to size up)
    {"name": "H&M", "relative_fit": 0.0},        # Runs true to size
    {"name": "Levi's", "relative_fit": 0.1},     # True to size / slightly large
    {"name": "Adidas", "relative_fit": 0.2},     # Runs slightly large
    {"name": "Patagonia", "relative_fit": 0.5},  # Runs large (needs to size down)
]

PRODUCTS_DATA = [
    # Nike
    {
        "brand_name": "Nike",
        "name": "Club Fleece Hoodie",
        "category": "Hoodies",
        "subcategory": "Pullover",
        "description": "Standard fit pullover hoodie made from soft brushed-back fleece for comfort.",
        "image_url": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?q=80&w=600&auto=format&fit=crop",
        "price": 65.0,
        "currency": "USD",
        "silhouette_type": "regular",
        "structure_level": "soft",
        "color_family": "grey",
        "visual_density": "minimal",
        "fabric_drape": "heavy"
    },
    {
        "brand_name": "Nike",
        "name": "Dri-FIT Slim Tee",
        "category": "T-Shirts",
        "subcategory": "Activewear",
        "description": "Slim-fit lightweight athletic shirt designed to keep you dry and comfortable.",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?q=80&w=600&auto=format&fit=crop",
        "price": 35.0,
        "currency": "USD",
        "silhouette_type": "slim",
        "structure_level": "soft",
        "color_family": "black",
        "visual_density": "minimal",
        "fabric_drape": "fluid"
    },
    # Zara
    {
        "brand_name": "Zara",
        "name": "Oversized Denim Jacket",
        "category": "Jackets",
        "subcategory": "Denim",
        "description": "Loose-fitting denim jacket with a relaxed collar and multiple pockets. Runs small, typical Zara fit.",
        "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?q=80&w=600&auto=format&fit=crop",
        "price": 89.90,
        "currency": "USD",
        "silhouette_type": "oversized",
        "structure_level": "structured",
        "color_family": "blue",
        "visual_density": "detailed",
        "fabric_drape": "stiff"
    },
    {
        "brand_name": "Zara",
        "name": "Structured Oxford Shirt",
        "category": "Shirts",
        "subcategory": "Formal",
        "description": "Fitted oxford shirt in structured cotton. A clean, close-fitting silhouette for formal and casual occasions.",
        "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?q=80&w=600&auto=format&fit=crop",
        "price": 49.90,
        "currency": "USD",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "white",
        "visual_density": "minimal",
        "fabric_drape": "stiff"
    },
    # H&M
    {
        "brand_name": "H&M",
        "name": "Relaxed Fit Cotton T-Shirt",
        "category": "T-Shirts",
        "subcategory": "Casual",
        "description": "Classic relaxed-fit t-shirt in soft organic cotton. Great drape and easy movement.",
        "image_url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?q=80&w=600&auto=format&fit=crop",
        "price": 14.99,
        "currency": "USD",
        "silhouette_type": "relaxed",
        "structure_level": "soft",
        "color_family": "white",
        "visual_density": "minimal",
        "fabric_drape": "fluid"
    },
    {
        "brand_name": "H&M",
        "name": "Straight Fit Chinos",
        "category": "Trousers",
        "subcategory": "Chinos",
        "description": "Straight-cut chinos in stretch cotton twill. Side and back pockets, zip fly.",
        "image_url": "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?q=80&w=600&auto=format&fit=crop",
        "price": 29.99,
        "currency": "USD",
        "silhouette_type": "straight",
        "structure_level": "balanced",
        "color_family": "beige",
        "visual_density": "minimal",
        "fabric_drape": "stiff"
    },
    # Levi's
    {
        "brand_name": "Levi's",
        "name": "501 Original Fit Jeans",
        "category": "Jeans",
        "subcategory": "Classic",
        "description": "The original straight fit jean since 1873. Rigid denim with a button fly and iconic styling.",
        "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?q=80&w=600&auto=format&fit=crop",
        "price": 98.00,
        "currency": "USD",
        "silhouette_type": "straight",
        "structure_level": "structured",
        "color_family": "blue",
        "visual_density": "detailed",
        "fabric_drape": "stiff"
    },
    {
        "brand_name": "Levi's",
        "name": "512 Slim Taper Jeans",
        "category": "Jeans",
        "subcategory": "Modern",
        "description": "Slim fit through the thigh tapering down to the ankle. Added stretch for comfortable everyday wear.",
        "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?q=80&w=600&auto=format&fit=crop",
        "price": 89.50,
        "currency": "USD",
        "silhouette_type": "slim",
        "structure_level": "balanced",
        "color_family": "dark",
        "visual_density": "detailed",
        "fabric_drape": "stiff"
    },
    # Adidas
    {
        "brand_name": "Adidas",
        "name": "Adicolor Classics Track Jacket",
        "category": "Jackets",
        "subcategory": "Activewear",
        "description": "Regular-fit retro style track jacket with the iconic 3-stripes. Slightly oversized cut.",
        "image_url": "https://images.unsplash.com/photo-1548883354-7622d03aca27?q=80&w=600&auto=format&fit=crop",
        "price": 75.00,
        "currency": "USD",
        "silhouette_type": "relaxed",
        "structure_level": "balanced",
        "color_family": "blue",
        "visual_density": "detailed",
        "fabric_drape": "fluid"
    },
    # Patagonia
    {
        "brand_name": "Patagonia",
        "name": "Better Sweater Fleece",
        "category": "Sweaters",
        "subcategory": "Outdoor",
        "description": "Warm, low-bulk quarter-zip jacket made of soft polyester fleece. Relaxed, runs generous.",
        "image_url": "https://images.unsplash.com/photo-1508445822-b8f81ca1d4f8?q=80&w=600&auto=format&fit=crop",
        "price": 139.00,
        "currency": "USD",
        "silhouette_type": "relaxed",
        "structure_level": "soft",
        "color_family": "green",
        "visual_density": "minimal",
        "fabric_drape": "heavy"
    }
]

async def seed():
    # Import all models to register them on Base
    from app.models import (  # noqa: F401
        User, FitProfile, FitAttribute, ClosetItem,
        Brand, Product, ProductVariant, Purchase,
        FitFeedback, Recommendation, RecommendationEvent,
    )
    
    print("Initializing tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # Clear existing database records for a clean seed
        from sqlalchemy import delete
        print("Clearing existing data...")
        await db.execute(delete(ProductVariant))
        await db.execute(delete(Product))
        await db.execute(delete(Brand))
        await db.commit()

        print("Seeding Brands...")
        brand_map = {}
        for b_data in BRANDS_DATA:
            brand = Brand(name=b_data["name"], relative_fit=b_data["relative_fit"], confidence=0.8)
            db.add(brand)
            await db.commit()
            await db.refresh(brand)
            brand_map[brand.name] = brand.id
            print(f"Created brand: {brand.name} ({brand.id})")

        print("Seeding Products and Variants...")
        for p_data in PRODUCTS_DATA:
            b_name = p_data.pop("brand_name")
            brand_id = brand_map[b_name]
            
            product = Product(
                brand_id=brand_id,
                name=p_data["name"],
                category=p_data["category"],
                subcategory=p_data.get("subcategory"),
                description=p_data.get("description"),
                image_url=p_data.get("image_url"),
                price=p_data["price"],
                currency=p_data["currency"],
                silhouette_type=p_data["silhouette_type"],
                structure_level=p_data["structure_level"],
                color_family=p_data["color_family"],
                visual_density=p_data["visual_density"],
                fabric_drape=p_data.get("fabric_drape")
            )
            db.add(product)
            await db.commit()
            await db.refresh(product)
            print(f"Created product: {product.name} ({product.id})")

            # Create variants based on category
            category_lower = product.category.lower()
            is_bottom = any(kw in category_lower for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
            
            if is_bottom:
                sizes = ["30", "31", "32", "33", "34", "36"]
                for size in sizes:
                    variant = ProductVariant(
                        product_id=product.id,
                        size_label=size,
                        color=product.color_family,
                        fabric="Stretch Denim" if "jean" in category_lower else "Cotton Twill",
                        stretch=0.2 if "jean" in category_lower else 0.1,
                        waist_ease=1.5,
                        inseam=32.0,
                    )
                    db.add(variant)
            else:
                sizes = ["XS", "S", "M", "L", "XL", "XXL"]
                for size in sizes:
                    variant = ProductVariant(
                        product_id=product.id,
                        size_label=size,
                        color=product.color_family,
                        fabric="Soft Fleece" if "hoodie" in category_lower else "Cotton",
                        stretch=0.1,
                        chest_ease=2.0,
                        shoulder_width=18.0 if size == "M" else 17.0 if size == "S" else 19.0,
                    )
                    db.add(variant)
            await db.commit()
            print(f"  Created variants for {product.name}")

        print("Seeding Complete!")

if __name__ == "__main__":
    asyncio.run(seed())
