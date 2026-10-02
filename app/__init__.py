from flask import Flask
from .config import Config
from .extensions import db, login_manager

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
        
    return app


def _init_db_data():
    from app.models.brand import Brand
    from app.models.product import Product, ProductVariant

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
        ]

        products_data = [
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
                "price": 98.00,
                "currency": "USD",
                "silhouette_type": "straight",
                "structure_level": "structured",
                "color_family": "blue",
                "visual_density": "detailed",
                "fabric_drape": "stiff"
            }
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

