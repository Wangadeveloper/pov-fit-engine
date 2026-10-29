from flask import Flask, request as flask_request, session as flask_session
from flask_login import login_user
from .config import Config
from .extensions import db, login_manager

# ── Review-mode flag ──────────────────────────────────────────────────────────
# Set to True to bypass all authentication (demo / review builds).
# Flip to False to restore normal login-required behaviour.
#
# Per-session isolation: when AUTH_DISABLED is True every browser session gets
# its own unique demo user (demo-<uuid>@pov.app) stored in the Flask session
# cookie. Profiles are therefore completely isolated per session/browser.
AUTH_DISABLED = True
# ─────────────────────────────────────────────────────────────────────────────


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)

    # Ensure all models are imported so SQLAlchemy registers tables
    from . import models  # noqa: F401
    
    with app.app_context():
        try:
            db.create_all()
            _init_db_data()
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
    
    # Import and register blueprints
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.shop import shop_bp
    from .routes.closet import closet_bp
    from .routes.fit import fit_bp
    from .routes.profile import profile_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(closet_bp)
    app.register_blueprint(fit_bp)
    app.register_blueprint(profile_bp)
    
    # User loader callback for Flask-Login
    import uuid
    from .models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, uuid.UUID(user_id))
        except (ValueError, TypeError):
            return None

    # ── Review-mode: auto-login per-session demo user on every request ────────
    # Each browser session gets its own isolated User row so that fit-profile
    # updates in one window/tab never bleed into another.
    if AUTH_DISABLED:
        @app.before_request
        def auto_login_session_user():
            from flask_login import current_user
            if not current_user.is_authenticated:
                user = _get_or_create_session_user()
                if user:
                    login_user(user, remember=True)
    # ─────────────────────────────────────────────────────────────────────────
        
    return app


def _get_or_create_session_user():
    """
    Return (and if needed create) a User that is unique to this browser session.

    The user's UUID is persisted in the Flask session cookie under the key
    'demo_user_id'.  On the very first visit a new User row is inserted with
    email demo-<uuid>@pov.app.  On subsequent requests the same row is reused,
    giving every browser tab/window its own isolated fit profile.
    """
    import uuid as _uuid
    import bcrypt
    from .models.user import User

    raw_id = flask_session.get('demo_user_id')

    # Try to load an existing session user
    if raw_id:
        try:
            uid = _uuid.UUID(raw_id)
            user = db.session.get(User, uid)
            if user:
                return user
        except (ValueError, TypeError):
            pass

    # Create a brand-new user for this session
    new_id = _uuid.uuid4()
    email = f"demo-{new_id.hex[:12]}@pov.app"
    hashed = bcrypt.hashpw(b"session-demo", bcrypt.gensalt()).decode()
    user = User(id=new_id, email=email, hashed_password=hashed)
    db.session.add(user)
    try:
        db.session.commit()
        flask_session['demo_user_id'] = str(new_id)
        flask_session.permanent = True
    except Exception:
        db.session.rollback()
        return None
    return user


def _init_db_data():
    from app.models.brand import Brand
    from app.models.product import Product, ProductVariant
    from sqlalchemy import text

    # Ensure tables have new columns on existing SQLite databases
    try:
        with db.engine.connect() as conn:
            # Check fit_profiles
            res = conn.execute(text("PRAGMA table_info(fit_profiles)")).fetchall()
            cols = [r[1] for r in res]
            if cols:
                if 'cultural_interests' not in cols:
                    conn.execute(text("ALTER TABLE fit_profiles ADD COLUMN cultural_interests JSON DEFAULT '[]'"))
                if 'aesthetic_preference' not in cols:
                    conn.execute(text("ALTER TABLE fit_profiles ADD COLUMN aesthetic_preference VARCHAR(100) DEFAULT 'casual'"))
                if 'occasions' not in cols:
                    conn.execute(text("ALTER TABLE fit_profiles ADD COLUMN occasions JSON DEFAULT '[]'"))
                if 'budget_tier' not in cols:
                    conn.execute(text("ALTER TABLE fit_profiles ADD COLUMN budget_tier VARCHAR(50) DEFAULT 'accessible'"))
                conn.commit()

            # Check recommendations
            rec_res = conn.execute(text("PRAGMA table_info(recommendations)")).fetchall()
            rec_cols = [r[1] for r in rec_res]
            if rec_cols:
                if 'cultural_score' not in rec_cols:
                    conn.execute(text("ALTER TABLE recommendations ADD COLUMN cultural_score FLOAT"))
                if 'cultural_rationale' not in rec_cols:
                    conn.execute(text("ALTER TABLE recommendations ADD COLUMN cultural_rationale VARCHAR(1000)"))
                if 'recommendation_type' not in rec_cols:
                    conn.execute(text("ALTER TABLE recommendations ADD COLUMN recommendation_type VARCHAR(50) DEFAULT 'qloo_enhanced'"))
                conn.commit()

            # Check recommendation_events
            ev_res = conn.execute(text("PRAGMA table_info(recommendation_events)")).fetchall()
            ev_cols = [r[1] for r in ev_res]
            if ev_cols:
                if 'recommendation_type' not in ev_cols:
                    conn.execute(text("ALTER TABLE recommendation_events ADD COLUMN recommendation_type VARCHAR(50) DEFAULT 'qloo_enhanced'"))
                conn.commit()

            # Check products
            prod_res = conn.execute(text("PRAGMA table_info(products)")).fetchall()
            prod_cols = [r[1] for r in prod_res]
            if prod_cols:
                if 'target_gender' not in prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN target_gender VARCHAR(20) NOT NULL DEFAULT 'unisex'"))
                conn.commit()
    except Exception:
        pass

    try:
        # Check if products already exist
        if db.session.query(Product).first():
            return

        brands_data = [
            {"name": "Nike", "relative_fit": -0.2},
            {"name": "Zara", "relative_fit": -0.6},
            {"name": "H&M", "relative_fit": 0.0},
            {"name": "Levi's", "relative_fit": 0.1},
            {"name": "Adidas", "relative_fit": 0.2},
            {"name": "Patagonia", "relative_fit": 0.5},
            # Fashion brands (committed images in app/static/product_images/)
            {"name": "7th Earth Studios", "relative_fit": -0.1},
            {"name": "Selara Studio", "relative_fit": -0.3},
            {"name": "Epic Threads US", "relative_fit": 0.1},
            {"name": "Bella Chix Co", "relative_fit": 0.0},
            {"name": "T Fashion Mart", "relative_fit": 0.1},
            {"name": "Kinini Tailoring Studio", "relative_fit": 0.0},
            {"name": "LingoStyles", "relative_fit": 0.0},
            {"name": "The Fashion People", "relative_fit": 0.1},
            {"name": "Vaapop", "relative_fit": 0.1},
            {"name": "POV Studio", "relative_fit": 0.0},
        ]

        products_data = [
            # ── Original catalog (Unsplash images) ──────────────────────────
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
            {
                "brand_name": "Zara",
                "name": "Oversized Denim Jacket",
                "category": "Jackets",
                "subcategory": "Denim",
                "description": "Loose-fitting denim jacket with a relaxed collar and multiple pockets. Runs small.",
                "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?q=80&w=600&auto=format&fit=crop",
                "price": 59.99,
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
                "description": "Fitted oxford shirt in structured cotton. A clean silhouette.",
                "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?q=80&w=600&auto=format&fit=crop",
                "price": 49.90,
                "currency": "USD",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "white",
                "visual_density": "minimal",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "H&M",
                "name": "Relaxed Fit Cotton T-Shirt",
                "category": "T-Shirts",
                "subcategory": "Casual",
                "description": "Classic relaxed-fit t-shirt in soft organic cotton. Great drape.",
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
                "brand_name": "Levi's",
                "name": "501 Original Fit Jeans",
                "category": "Jeans",
                "subcategory": "Classic",
                "description": "The original straight fit jean since 1873.",
                "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?q=80&w=600&auto=format&fit=crop",
                "price": 69.99,
                "currency": "USD",
                "silhouette_type": "straight",
                "structure_level": "structured",
                "color_family": "blue",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            # ── Fashion products (images committed to app/static/product_images/) ──
            {
                "brand_name": "7th Earth Studios",
                "name": "Heavy Oversized Black T-Shirt",
                "category": "T-Shirts",
                "subcategory": "Oversized",
                "description": "A premium heavyweight oversized black tee with a relaxed dropped-shoulder silhouette. Ideal for streetwear and minimalist layering.",
                "image_url": "/static/product_images/heavy_oversized_black_tshirt.jpeg",
                "price": 29.00,
                "currency": "USD",
                "silhouette_type": "oversized",
                "structure_level": "soft",
                "color_family": "dark",
                "visual_density": "minimal",
                "fabric_drape": "heavy"
            },
            {
                "brand_name": "Selara Studio",
                "name": "Beige Tailored Blazer",
                "category": "Jackets",
                "subcategory": "Blazers",
                "description": "A structured beige blazer with clean lapels and a slim silhouette. Perfect for smart-casual and professional looks.",
                "image_url": "/static/product_images/beige_tailored_blazer.jpeg",
                "price": 65.00,
                "currency": "USD",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "neutral",
                "visual_density": "minimal",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "Epic Threads US",
                "name": "Vintage Graphic Hoodie",
                "category": "Hoodies",
                "subcategory": "Graphic",
                "description": "A washed-out vintage graphic hoodie with urban streetwear energy. Relaxed fit with bold retro print.",
                "image_url": "/static/product_images/vintage_graphic_hoodie.jpeg",
                "price": 48.00,
                "currency": "USD",
                "silhouette_type": "relaxed",
                "structure_level": "soft",
                "color_family": "neutral",
                "visual_density": "detailed",
                "fabric_drape": "heavy"
            },
            {
                "brand_name": "Bella Chix Co",
                "name": "Floral Midi Dress",
                "category": "Dresses",
                "subcategory": "Midi",
                "description": "A romantic floral midi dress with delicate print and fluid silhouette. Great for summer occasions and feminine styling.",
                "image_url": "/static/product_images/floral_midi_dress.jpeg",
                "price": 57.00,
                "currency": "USD",
                "silhouette_type": "regular",
                "structure_level": "soft",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "T Fashion Mart",
                "name": "Khaki Cargo Trousers",
                "category": "Trousers",
                "subcategory": "Cargo",
                "description": "Utilitarian khaki cargo trousers with multiple pockets and a relaxed straight-leg fit. Perfect for streetwear and adventure outfits.",
                "image_url": "/static/product_images/khaki_cargo_trousers.jpeg",
                "price": 59.00,
                "currency": "USD",
                "silhouette_type": "relaxed",
                "structure_level": "balanced",
                "color_family": "neutral",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "Kinini Tailoring Studio",
                "name": "Contemporary Kenyan Coordinated Set",
                "category": "Sets",
                "subcategory": "Co-ords",
                "description": "Contemporary Kenyan fashion featuring tailored dresses, trousers, and coordinated sets with a modern African aesthetic.",
                "image_url": "/static/product_images/kinini_tailoring_studio.jpeg",
                "price": 2800.0,
                "currency": "KES",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "LingoStyles",
                "name": "Ankara Puff-Sleeve Top",
                "category": "Tops",
                "subcategory": "Ankara",
                "description": "Vibrant Ankara puff-sleeve top with bold African prints. Part of a full collection including kitenge tops, jumpsuits, and two-piece sets.",
                "image_url": "/static/product_images/lingostyles_ankara_collection.jpeg",
                "price": 1500.0,
                "currency": "KES",
                "silhouette_type": "regular",
                "structure_level": "balanced",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "The Fashion People",
                "name": "African Men's Embroidered Shirt",
                "category": "Shirts",
                "subcategory": "African Print",
                "description": "Handcrafted African men's shirt with intricate embroidery. Also available as embroidered dresses and kaftans.",
                "image_url": "/static/product_images/the_fashion_people_african.jpeg",
                "price": 1800.0,
                "currency": "KES",
                "silhouette_type": "relaxed",
                "structure_level": "balanced",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "Vaapop",
                "name": "Vaapop Khaki Cargo Pants",
                "category": "Trousers",
                "subcategory": "Cargo",
                "description": "Thrifted-aesthetic khaki cargo pants from Vaapop. Also stock retro football jerseys, denim, and everyday streetwear.",
                "image_url": "/static/product_images/vaapop_streetwear.jpeg",
                "price": 1500.0,
                "currency": "KES",
                "silhouette_type": "relaxed",
                "structure_level": "balanced",
                "color_family": "neutral",
                "visual_density": "minimal",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "POV Studio",
                "name": "Baggy & Oversized Streetwear Set",
                "category": "Sets",
                "subcategory": "Streetwear",
                "description": "Loose silhouettes, relaxed fits, and urban style — featuring baggy cargo trousers, oversized graphic tees, wide-leg jeans, and oversized hoodies.",
                "image_url": "/static/product_images/baggy_oversized_streetwear_collection.jpeg",
                "price": 2200.0,
                "currency": "KES",
                "silhouette_type": "oversized",
                "structure_level": "soft",
                "color_family": "neutral",
                "visual_density": "detailed",
                "fabric_drape": "heavy"
            },
            {
                "brand_name": "POV Studio",
                "name": "Quiet Luxury Smart Casual Collection",
                "category": "Sets",
                "subcategory": "Smart Casual",
                "description": "Tailored trousers, neutral shirts, structured blazers, and understated knitwear for a quiet luxury aesthetic.",
                "image_url": "/static/product_images/quiet_luxury_collection.jpeg",
                "price": 2800.0,
                "currency": "KES",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "neutral",
                "visual_density": "minimal",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "POV Studio",
                "name": "African Contemporary Cultural Expression",
                "category": "Sets",
                "subcategory": "African Print",
                "description": "Ankara shirts, kitenge skirts, modern African-print dresses, and statement jackets for bold cultural expression.",
                "image_url": "/static/product_images/african_contemporary_collection.jpeg",
                "price": 2000.0,
                "currency": "KES",
                "silhouette_type": "regular",
                "structure_level": "balanced",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "POV Studio",
                "name": "Tight & Fitted Body-Conscious Collection",
                "category": "Sets",
                "subcategory": "Fitted",
                "description": "Body-conscious slim silhouettes — slim-fit tees, skinny jeans, ribbed tops, stretch shirts, and fitted knitwear.",
                "image_url": "/static/product_images/tight_fitted_clothing_collection.jpeg",
                "price": 1800.0,
                "currency": "KES",
                "silhouette_type": "slim",
                "structure_level": "balanced",
                "color_family": "neutral",
                "visual_density": "minimal",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "POV Studio",
                "name": "Expressive Gender-Fluid Statement Collection",
                "category": "Sets",
                "subcategory": "Gender Fluid",
                "description": "Crop tops, mesh shirts, pearl necklaces, bold colours, graphic prints, flared trousers, and unconventional layering.",
                "image_url": "/static/product_images/expressive_playful_collection.jpeg",
                "price": 2200.0,
                "currency": "KES",
                "silhouette_type": "regular",
                "structure_level": "soft",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "POV Studio",
                "name": "Urban Streetwear Collection",
                "category": "Sets",
                "subcategory": "Streetwear",
                "description": "Oversized tees, hoodies, baggy jeans, cargo pants, and graphic prints for authentic urban casual style.",
                "image_url": "/static/product_images/streetwear_collection.jpeg",
                "price": 1800.0,
                "currency": "KES",
                "silhouette_type": "oversized",
                "structure_level": "soft",
                "color_family": "dark",
                "visual_density": "detailed",
                "fabric_drape": "heavy"
            },
            {
                "brand_name": "POV Studio",
                "name": "Alternative Punk & Edgy Collection",
                "category": "Sets",
                "subcategory": "Alternative",
                "description": "Leather-look jackets, distressed skinny jeans, graphic band tees, buckled boots, and chain accessories.",
                "image_url": "/static/product_images/alternative_punk_edgy_collection.jpeg",
                "price": 2500.0,
                "currency": "KES",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "dark",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "POV Studio",
                "name": "Elegant Occasionwear Formal Collection",
                "category": "Dresses",
                "subcategory": "Formal",
                "description": "Satin dresses, evening gowns, coordinated sets, and polished formal outfits for elegant occasions.",
                "image_url": "/static/product_images/elegant_occasionwear_collection.jpeg",
                "price": 2800.0,
                "currency": "KES",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "neutral",
                "visual_density": "minimal",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "POV Studio",
                "name": "African Contemporary Modern Cut Collection",
                "category": "Sets",
                "subcategory": "Afro Fusion",
                "description": "Oversized Ankara shirts, fitted African-print tops, wide-leg trousers, and bold-print jackets in modern fusion cuts.",
                "image_url": "/static/product_images/african_contemporary_modern_collection.jpeg",
                "price": 2200.0,
                "currency": "KES",
                "silhouette_type": "oversized",
                "structure_level": "balanced",
                "color_family": "bold",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "POV Studio",
                "name": "Vintage & Retro Nostalgic Collection",
                "category": "Sets",
                "subcategory": "Vintage",
                "description": "Vintage denim jackets, retro graphic tees, relaxed jeans, and throwback silhouettes for nostalgic aesthetics.",
                "image_url": "/static/product_images/vintage_retro_collection.jpeg",
                "price": 1800.0,
                "currency": "KES",
                "silhouette_type": "relaxed",
                "structure_level": "balanced",
                "color_family": "neutral",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            },
            {
                "brand_name": "POV Studio",
                "name": "Athleisure Sporty Everyday Collection",
                "category": "Sets",
                "subcategory": "Athleisure",
                "description": "Matching tracksuits, leggings, sporty jackets, and comfortable everyday sets for the active lifestyle.",
                "image_url": "/static/product_images/athleisure_collection.jpeg",
                "price": 1800.0,
                "currency": "KES",
                "silhouette_type": "relaxed",
                "structure_level": "soft",
                "color_family": "bold",
                "visual_density": "minimal",
                "fabric_drape": "fluid"
            },
            {
                "brand_name": "POV Studio",
                "name": "Slim Tailoring & Elevated Basics",
                "category": "Sets",
                "subcategory": "Smart Casual",
                "description": "Tailored slim trousers, fitted turtlenecks, slim blazers, and monochrome matching sets for a clean polished look.",
                "image_url": "/static/product_images/slim_tailoring_elevated_basics.jpeg",
                "price": 2200.0,
                "currency": "KES",
                "silhouette_type": "slim",
                "structure_level": "structured",
                "color_family": "neutral",
                "visual_density": "minimal",
                "fabric_drape": "stiff"
            },
        ]

        brand_map = {}
        for b_data in brands_data:
            brand = Brand(name=b_data["name"], relative_fit=b_data["relative_fit"], confidence=0.8)
            db.session.add(brand)
            db.session.commit()
            brand_map[brand.name] = brand.id

        for p_data in products_data:
            b_name = p_data.pop("brand_name")
            brand_id = brand_map.get(b_name)
            if not brand_id:
                continue

            product = Product(brand_id=brand_id, **p_data)
            db.session.add(product)
            db.session.commit()

            category_lower = product.category.lower()
            is_bottom = any(kw in category_lower for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
            sizes = ["30", "31", "32", "33", "34", "36"] if is_bottom else ["XS", "S", "M", "L", "XL"]

            for size in sizes:
                variant = ProductVariant(
                    product_id=product.id,
                    size_label=size,
                    color=product.color_family,
                    fabric="Cotton",
                    stretch=0.1,
                )
                db.session.add(variant)
            db.session.commit()
    except Exception:
        db.session.rollback()

