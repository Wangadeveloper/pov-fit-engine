"""
seed_fashion_products.py
───────────────────────────────────────────────────────────────────────────────
Seeds the 21 new fashion products from 'Add Fashion Products_files/' into the
POV database. Images have already been copied to app/static/product_images/.

Run with:
    source venv/bin/activate
    python seed_fashion_products.py
"""

import os
import uuid
import shutil
from pathlib import Path

# ── Bootstrap Flask app ──────────────────────────────────────────────────────
from app import create_app
from app.extensions import db
from app.models.brand import Brand
from app.models.product import Product, ProductVariant

app = create_app()

# ── Image source / destination ───────────────────────────────────────────────
SRC_DIR = Path("Add Fashion Products_files")
DST_DIR = Path("app/static/product_images")
DST_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(prefix: str) -> str:
    """Convert a long descriptive filename prefix to a short slug for URL use."""
    slugs = {
        "1. Baggy & oversized streetwear": "baggy_oversized_streetwear_collection",
        "1. Heavy Oversized Black T-Shirt": "heavy_oversized_black_tshirt",
        "1. Quiet luxury": "quiet_luxury_collection",
        "2. African contemporary": "african_contemporary_collection",
        "2. Beige Tailored Blazer": "beige_tailored_blazer",
        "2. Tight & fitted clothing": "tight_fitted_clothing_collection",
        "3. Expressive": "expressive_playful_collection",
        "3. Streetwear": "streetwear_collection",
        "3. Vintage Graphic Hoodie": "vintage_graphic_hoodie",
        "4. Alternative, punk & edgy": "alternative_punk_edgy_collection",
        "4. Elegant occasionwear": "elegant_occasionwear_collection",
        "4. Floral Midi Dress": "floral_midi_dress",
        "5. African contemporary": "african_contemporary_modern_collection",
        "5. Khaki Cargo Trousers": "khaki_cargo_trousers",
        "5. Vintage and retro": "vintage_retro_collection",
        "6. Athleisure": "athleisure_collection",
        "6. Slim tailoring": "slim_tailoring_elevated_basics",
        "Kinini Tailoring Studio": "kinini_tailoring_studio",
        "LingoStyles": "lingostyles_ankara_collection",
        "The Fashion People": "the_fashion_people_african",
        "Vaapop": "vaapop_streetwear",
    }
    for key, slug in slugs.items():
        if prefix.startswith(key):
            return slug + ".jpeg"
    return prefix[:60].replace(" ", "_") + ".jpeg"


# ── Product definitions ───────────────────────────────────────────────────────
PRODUCTS = [
    # ── Individual items with explicit prices ────────────────────────────────
    {
        "img_prefix": "1. Heavy Oversized Black T-Shirt",
        "brand": "7th Earth Studios",
        "name": "Heavy Oversized Black T-Shirt",
        "category": "T-Shirts",
        "subcategory": "Oversized",
        "description": "A premium heavyweight oversized black tee with a relaxed dropped-shoulder silhouette. Ideal for streetwear and minimalist layering.",
        "price": 29.00,
        "currency": "USD",
        "silhouette_type": "oversized",
        "structure_level": "soft",
        "color_family": "dark",
        "visual_density": "minimal",
        "fabric_drape": "heavy",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.1,
    },
    {
        "img_prefix": "2. Beige Tailored Blazer",
        "brand": "Selara Studio",
        "name": "Beige Tailored Blazer",
        "category": "Jackets",
        "subcategory": "Blazers",
        "description": "A structured beige blazer with clean lapels and a slim silhouette. Perfect for smart-casual and professional looks.",
        "price": 65.00,
        "currency": "USD",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "neutral",
        "visual_density": "minimal",
        "fabric_drape": "stiff",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.0,
    },
    {
        "img_prefix": "3. Vintage Graphic Hoodie",
        "brand": "Epic Threads US",
        "name": "Vintage Graphic Hoodie",
        "category": "Hoodies",
        "subcategory": "Graphic",
        "description": "A washed-out vintage graphic hoodie with urban streetwear energy. Relaxed fit with bold retro print.",
        "price": 48.00,
        "currency": "USD",
        "silhouette_type": "relaxed",
        "structure_level": "soft",
        "color_family": "neutral",
        "visual_density": "detailed",
        "fabric_drape": "heavy",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.2,
    },
    {
        "img_prefix": "4. Floral Midi Dress",
        "brand": "Bella Chix Co",
        "name": "Floral Midi Dress",
        "category": "Dresses",
        "subcategory": "Midi",
        "description": "A romantic floral midi dress with delicate print and fluid silhouette. Great for summer occasions and feminine styling.",
        "price": 57.00,
        "currency": "USD",
        "silhouette_type": "regular",
        "structure_level": "soft",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.15,
    },
    {
        "img_prefix": "5. Khaki Cargo Trousers",
        "brand": "T Fashion Mart",
        "name": "Khaki Cargo Trousers",
        "category": "Trousers",
        "subcategory": "Cargo",
        "description": "Utilitarian khaki cargo trousers with multiple pockets and a relaxed straight-leg fit. Perfect for streetwear and adventure outfits.",
        "price": 59.00,
        "currency": "USD",
        "silhouette_type": "relaxed",
        "structure_level": "balanced",
        "color_family": "neutral",
        "visual_density": "detailed",
        "fabric_drape": "stiff",
        "sizes": ["28", "30", "32", "34", "36"],
        "stretch": 0.05,
    },
    # ── Kenyan / African brands ──────────────────────────────────────────────
    {
        "img_prefix": "Kinini Tailoring Studio",
        "brand": "Kinini Tailoring Studio",
        "name": "Contemporary Kenyan Coordinated Set",
        "category": "Sets",
        "subcategory": "Co-ords",
        "description": "Contemporary Kenyan fashion featuring tailored dresses, trousers, and coordinated sets with a modern African aesthetic.",
        "price": 2800.0,
        "currency": "KES",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.1,
    },
    {
        "img_prefix": "LingoStyles",
        "brand": "LingoStyles",
        "name": "Ankara Puff-Sleeve Top",
        "category": "Tops",
        "subcategory": "Ankara",
        "description": "Vibrant Ankara puff-sleeve top with bold African prints. Part of a full collection including kitenge tops, jumpsuits, and two-piece sets.",
        "price": 1500.0,
        "currency": "KES",
        "silhouette_type": "regular",
        "structure_level": "balanced",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "stiff",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "stretch": 0.05,
    },
    {
        "img_prefix": "The Fashion People",
        "brand": "The Fashion People",
        "name": "African Men's Embroidered Shirt",
        "category": "Shirts",
        "subcategory": "African Print",
        "description": "Handcrafted African men's shirt with intricate embroidery. Also available as embroidered dresses and kaftans.",
        "price": 1800.0,
        "currency": "KES",
        "silhouette_type": "relaxed",
        "structure_level": "balanced",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "fluid",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.0,
    },
    {
        "img_prefix": "Vaapop",
        "brand": "Vaapop",
        "name": "Vaapop Khaki Cargo Pants",
        "category": "Trousers",
        "subcategory": "Cargo",
        "description": "Thrifted-aesthetic khaki cargo pants from Vaapop. Also stock retro football jerseys, denim, and everyday streetwear.",
        "price": 1500.0,
        "currency": "KES",
        "silhouette_type": "relaxed",
        "structure_level": "balanced",
        "color_family": "neutral",
        "visual_density": "minimal",
        "fabric_drape": "stiff",
        "sizes": ["28", "30", "32", "34", "36"],
        "stretch": 0.05,
    },
    # ── Style-collection / mood-board cards ──────────────────────────────────
    {
        "img_prefix": "1. Baggy & oversized streetwear",
        "brand": "POV Studio",
        "name": "Baggy & Oversized Streetwear Set",
        "category": "Sets",
        "subcategory": "Streetwear",
        "description": "Loose silhouettes, relaxed fits, and urban style — featuring baggy cargo trousers, oversized graphic tees, wide-leg jeans, and oversized hoodies.",
        "price": 2200.0,
        "currency": "KES",
        "silhouette_type": "oversized",
        "structure_level": "soft",
        "color_family": "neutral",
        "visual_density": "detailed",
        "fabric_drape": "heavy",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.1,
    },
    {
        "img_prefix": "1. Quiet luxury",
        "brand": "POV Studio",
        "name": "Quiet Luxury Smart Casual Collection",
        "category": "Sets",
        "subcategory": "Smart Casual",
        "description": "Tailored trousers, neutral shirts, structured blazers, and understated knitwear for a quiet luxury aesthetic.",
        "price": 2800.0,
        "currency": "KES",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "neutral",
        "visual_density": "minimal",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.0,
    },
    {
        "img_prefix": "2. African contemporary",
        "brand": "POV Studio",
        "name": "African Contemporary Cultural Expression",
        "category": "Sets",
        "subcategory": "African Print",
        "description": "Ankara shirts, kitenge skirts, modern African-print dresses, and statement jackets for bold cultural expression.",
        "price": 2000.0,
        "currency": "KES",
        "silhouette_type": "regular",
        "structure_level": "balanced",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "stiff",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "stretch": 0.05,
    },
    {
        "img_prefix": "2. Tight & fitted clothing",
        "brand": "POV Studio",
        "name": "Tight & Fitted Body-Conscious Collection",
        "category": "Sets",
        "subcategory": "Fitted",
        "description": "Body-conscious slim silhouettes — slim-fit tees, skinny jeans, ribbed tops, stretch shirts, and fitted knitwear.",
        "price": 1800.0,
        "currency": "KES",
        "silhouette_type": "slim",
        "structure_level": "balanced",
        "color_family": "neutral",
        "visual_density": "minimal",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.6,
    },
    {
        "img_prefix": "3. Expressive",
        "brand": "POV Studio",
        "name": "Expressive Gender-Fluid Statement Collection",
        "category": "Sets",
        "subcategory": "Gender Fluid",
        "description": "Crop tops, mesh shirts, pearl necklaces, bold colours, graphic prints, flared trousers, and unconventional layering.",
        "price": 2200.0,
        "currency": "KES",
        "silhouette_type": "regular",
        "structure_level": "soft",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.2,
    },
    {
        "img_prefix": "3. Streetwear",
        "brand": "POV Studio",
        "name": "Urban Streetwear Collection",
        "category": "Sets",
        "subcategory": "Streetwear",
        "description": "Oversized tees, hoodies, baggy jeans, cargo pants, and graphic prints for authentic urban casual style.",
        "price": 1800.0,
        "currency": "KES",
        "silhouette_type": "oversized",
        "structure_level": "soft",
        "color_family": "dark",
        "visual_density": "detailed",
        "fabric_drape": "heavy",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.1,
    },
    {
        "img_prefix": "4. Alternative, punk & edgy",
        "brand": "POV Studio",
        "name": "Alternative Punk & Edgy Collection",
        "category": "Sets",
        "subcategory": "Alternative",
        "description": "Leather-look jackets, distressed skinny jeans, graphic band tees, buckled boots, and chain accessories.",
        "price": 2500.0,
        "currency": "KES",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "dark",
        "visual_density": "detailed",
        "fabric_drape": "stiff",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.15,
    },
    {
        "img_prefix": "4. Elegant occasionwear",
        "brand": "POV Studio",
        "name": "Elegant Occasionwear Formal Collection",
        "category": "Dresses",
        "subcategory": "Formal",
        "description": "Satin dresses, evening gowns, coordinated sets, and polished formal outfits for elegant occasions.",
        "price": 2800.0,
        "currency": "KES",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "neutral",
        "visual_density": "minimal",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.0,
    },
    {
        "img_prefix": "5. African contemporary",
        "brand": "POV Studio",
        "name": "African Contemporary Modern Cut Collection",
        "category": "Sets",
        "subcategory": "Afro Fusion",
        "description": "Oversized Ankara shirts, fitted African-print tops, wide-leg trousers, and bold-print jackets in modern fusion cuts.",
        "price": 2200.0,
        "currency": "KES",
        "silhouette_type": "oversized",
        "structure_level": "balanced",
        "color_family": "bold",
        "visual_density": "detailed",
        "fabric_drape": "stiff",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.05,
    },
    {
        "img_prefix": "5. Vintage and retro",
        "brand": "POV Studio",
        "name": "Vintage & Retro Nostalgic Collection",
        "category": "Sets",
        "subcategory": "Vintage",
        "description": "Vintage denim jackets, retro graphic tees, relaxed jeans, and throwback silhouettes for nostalgic aesthetics.",
        "price": 1800.0,
        "currency": "KES",
        "silhouette_type": "relaxed",
        "structure_level": "balanced",
        "color_family": "neutral",
        "visual_density": "detailed",
        "fabric_drape": "stiff",
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "stretch": 0.1,
    },
    {
        "img_prefix": "6. Athleisure",
        "brand": "POV Studio",
        "name": "Athleisure Sporty Everyday Collection",
        "category": "Sets",
        "subcategory": "Athleisure",
        "description": "Matching tracksuits, leggings, sporty jackets, and comfortable everyday sets for the active lifestyle.",
        "price": 1800.0,
        "currency": "KES",
        "silhouette_type": "relaxed",
        "structure_level": "soft",
        "color_family": "bold",
        "visual_density": "minimal",
        "fabric_drape": "fluid",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "stretch": 0.7,
    },
    {
        "img_prefix": "6. Slim tailoring",
        "brand": "POV Studio",
        "name": "Slim Tailoring & Elevated Basics",
        "category": "Sets",
        "subcategory": "Smart Casual",
        "description": "Tailored slim trousers, fitted turtlenecks, slim blazers, and monochrome matching sets for a clean polished look.",
        "price": 2200.0,
        "currency": "KES",
        "silhouette_type": "slim",
        "structure_level": "structured",
        "color_family": "neutral",
        "visual_density": "minimal",
        "fabric_drape": "stiff",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "stretch": 0.0,
    },
]


def find_image_file(prefix: str) -> Path | None:
    """Find the JPEG file in Add Fashion Products_files whose name starts with prefix."""
    for f in SRC_DIR.iterdir():
        if f.suffix.lower() == ".jpeg" and f.name.startswith(prefix):
            return f
    return None


def get_or_create_brand(session, name: str) -> Brand:
    brand = session.execute(db.select(Brand).where(Brand.name == name)).scalars().first()
    if not brand:
        brand = Brand(name=name, relative_fit=0.0, confidence=0.5)
        session.add(brand)
        session.flush()
    return brand


def seed():
    added = 0
    skipped = 0
    with app.app_context():
        for p in PRODUCTS:
            # Check if already seeded (by name)
            existing = db.session.execute(
                db.select(Product).where(Product.name == p["name"])
            ).scalars().first()
            if existing:
                print(f"  [SKIP] Already exists: {p['name']}")
                skipped += 1
                continue

            # Copy image to static folder with clean slug name
            src = find_image_file(p["img_prefix"])
            if src:
                slug = safe_filename(p["img_prefix"])
                dst = DST_DIR / slug
                if not dst.exists():
                    import shutil
                    shutil.copy2(src, dst)
                image_url = f"/static/product_images/{slug}"
            else:
                print(f"  [WARN] No image found for prefix: {p['img_prefix']}")
                image_url = None

            brand = get_or_create_brand(db.session, p["brand"])

            product = Product(
                brand_id=brand.id,
                name=p["name"],
                category=p["category"],
                subcategory=p.get("subcategory"),
                description=p["description"],
                image_url=image_url,
                price=p["price"],
                currency=p["currency"],
                silhouette_type=p["silhouette_type"],
                structure_level=p["structure_level"],
                color_family=p["color_family"],
                visual_density=p["visual_density"],
                fabric_drape=p.get("fabric_drape"),
            )
            db.session.add(product)
            db.session.flush()  # get product.id

            # Add size variants
            for size in p.get("sizes", ["S", "M", "L", "XL"]):
                variant = ProductVariant(
                    product_id=product.id,
                    size_label=size,
                    stretch=p.get("stretch", 0.0),
                )
                db.session.add(variant)

            print(f"  [ADD] {p['name']} ({p['brand']}) -> {image_url}")
            added += 1

        db.session.commit()
        print(f"\nDone! Added {added} products, skipped {skipped} duplicates.")


if __name__ == "__main__":
    seed()
