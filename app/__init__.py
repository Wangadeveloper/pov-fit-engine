from flask import Flask
from .config import Config
from .extensions import db, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)
    
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
        except ValueError:
            return None
        
    return app
