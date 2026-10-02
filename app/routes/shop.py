from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.extensions import db
from app.models.product import Product, ProductVariant
from app.models.brand import Brand
from app.models.closet import ClosetItem
from app.services.recommendation_service import RecommendationService
from app.services.youcam_service import youcam_service
import uuid

shop_bp = Blueprint('shop', __name__, url_prefix='/shop')


@shop_bp.route('/')
def index():
    """Main shop page – show all products with POV fit scoring for logged-in users."""
    stmt = (
        select(Product)
        .options(selectinload(Product.brand), selectinload(Product.variants))
        .order_by(Product.created_at.desc())
    )
    products = db.session.execute(stmt).scalars().all()

    # For logged-in users, pre-compute POV fit scores for all products
    pov_scores = {}
    if current_user.is_authenticated:
        try:
            recs = RecommendationService.get_recommendations_for_products_batch(
                db, current_user.id, list(products)
            )
            for rec in recs:
                pov_scores[rec["product_id"]] = rec
        except Exception:
            pass  # Degrade gracefully — still show the shop

    return render_template('shop/index.html', products=products, pov_scores=pov_scores)


@shop_bp.route('/product/<uuid:product_id>')
def product_detail(product_id):
    """Product detail page with full POV analysis and virtual try-on."""
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.brand), selectinload(Product.variants))
    )
    product = db.session.execute(stmt).scalars().first()
    if not product:
        abort(404)

    pov_analysis = None
    if current_user.is_authenticated:
        try:
            pov_analysis = RecommendationService.get_recommendation_for_product(
                db, current_user.id, product_id
            )
        except Exception:
            pass

    return render_template('shop/product.html', product=product, pov_analysis=pov_analysis)


# ──────────────────────────────────────────────
# API: Fit with POV  (AJAX)
# ──────────────────────────────────────────────

@shop_bp.route('/api/fit-analysis/<uuid:product_id>', methods=['POST'])
@login_required
def api_fit_analysis(product_id):
    """
    Returns POV fit analysis for a product as JSON.
    Called by the "Fit with POV" button on product cards.
    """
    try:
        analysis = RecommendationService.get_recommendation_for_product(
            db, current_user.id, product_id
        )
        return jsonify({"success": True, "data": analysis})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": "POV engine error. Please try again."}), 500


# ──────────────────────────────────────────────
# API: Virtual Try-On (YouCam)
# ──────────────────────────────────────────────

@shop_bp.route('/api/virtual-tryon/<uuid:product_id>', methods=['POST'])
@login_required
def api_virtual_tryon(product_id):
    """
    Initiates a YouCam virtual try-on task.
    Requires user to have a try_on_photo_url in their fit profile.
    """
    from app.services.fit_service import FitService

    data = request.get_json() or {}
    user_photo_url = data.get('user_photo_url')

    # Load product
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.brand))
    )
    product = db.session.execute(stmt).scalars().first()
    if not product:
        return jsonify({"success": False, "error": "Product not found."}), 404

    if not product.image_url:
        return jsonify({"success": False, "error": "Product has no image for try-on."}), 400

    # Fall back to profile photo if none provided
    if not user_photo_url:
        profile = FitService.get_or_create_profile(db, current_user.id)
        user_photo_url = profile.try_on_photo_url

    if not user_photo_url:
        return jsonify({
            "success": False,
            "error": "Please upload a photo to your fit profile before using Virtual Try-On.",
            "action": "upload_photo"
        }), 400

    garment_category = youcam_service.map_category(product.category)

    result = youcam_service.create_tryon_task(
        user_photo_url=user_photo_url,
        garment_image_url=product.image_url,
        garment_category=garment_category,
    )

    return jsonify({
        "success": result["success"],
        "task_id": result.get("task_id"),
        "status": result.get("status"),
        "result_url": result.get("result_url"),
        "provider": result.get("provider"),
        "sandbox": result.get("sandbox", False),
        "sandbox_note": result.get("sandbox_note"),
        "product_name": product.name,
        "garment_image_url": product.image_url,
        "user_photo_url": user_photo_url,  # included so frontend can composite it
    })


@shop_bp.route('/api/virtual-tryon/status/<task_id>', methods=['GET'])
@login_required
def api_tryon_status(task_id):
    """Poll YouCam for try-on task status."""
    result = youcam_service.get_task_result(task_id)
    return jsonify(result)


# ──────────────────────────────────────────────
# Add to Wardrobe (Closet) from Try-On
# ──────────────────────────────────────────────

@shop_bp.route('/api/add-to-wardrobe/<uuid:product_id>', methods=['POST'])
@login_required
def api_add_to_wardrobe(product_id):
    """Add a product directly to the user's wardrobe (closet) after try-on."""
    stmt = select(Product).where(Product.id == product_id).options(selectinload(Product.brand))
    product = db.session.execute(stmt).scalars().first()
    if not product:
        return jsonify({"success": False, "error": "Product not found."}), 404

    data = request.get_json() or {}
    size_label = data.get('size_label', 'M')
    fit_rating = data.get('fit_rating', 'perfect')

    # Check if already in wardrobe
    existing = db.session.execute(
        select(ClosetItem).where(
            ClosetItem.user_id == current_user.id,
            ClosetItem.brand_name == (product.brand.name if product.brand else "Unknown"),
            ClosetItem.category == product.category,
            ClosetItem.size_label == size_label,
        )
    ).scalars().first()

    if existing:
        return jsonify({"success": False, "error": "This item is already in your wardrobe."}), 409

    item = ClosetItem(
        user_id=current_user.id,
        brand_name=product.brand.name if product.brand else "Unknown",
        category=product.category,
        subcategory=product.subcategory,
        size_label=size_label,
        color=None,
        fit_label=product.silhouette_type,
        fit_rating=fit_rating,
        tight_loose_regions={},
        image_url=product.image_url,
    )
    db.session.add(item)
    db.session.commit()

    return jsonify({"success": True, "message": f"{product.name} added to your wardrobe!"})
