import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select
from app.extensions import db
from app.models.closet import ClosetItem
from app.services.closet_service import ClosetService
from app.schemas.closet import ClosetItemCreate

closet_bp = Blueprint('closet', __name__, url_prefix='/closet')


@closet_bp.route('/')
@login_required
def index():
    """Display all wardrobe / closet items for the current user."""
    stmt = (
        select(ClosetItem)
        .where(ClosetItem.user_id == current_user.id)
        .order_by(ClosetItem.created_at.desc())
    )
    items = list(db.session.execute(stmt).scalars().all())
    return render_template('closet/index.html', items=items)


@closet_bp.route('/add', methods=['POST'])
@login_required
def add():
    """Add a new item to the user's wardrobe."""
    if request.is_json:
        data = request.get_json() or {}
        brand_name = data.get('brand_name', '').strip()
        category = data.get('category', '').strip()
        size_label = data.get('size_label', '').strip()
        if not brand_name or not category or not size_label:
            return jsonify({"success": False, "error": "Brand name, category, and size label are required."}), 400
        
        item_create = ClosetItemCreate(
            brand_name=brand_name,
            category=category,
            subcategory=data.get('subcategory'),
            size_label=size_label,
            color=data.get('color'),
            fit_label=data.get('fit_label', 'regular'),
            fit_rating=data.get('fit_rating', 'perfect'),
            tight_loose_regions=data.get('tight_loose_regions', {}),
            notes=data.get('notes'),
            image_url=data.get('image_url')
        )
        item = ClosetService.add_item(db, current_user.id, item_create)
        return jsonify({"success": True, "message": "Item added to your wardrobe!", "item_id": str(item.id)})
    
    # Form submission fallback
    brand_name = request.form.get('brand_name', '').strip()
    category = request.form.get('category', '').strip()
    size_label = request.form.get('size_label', '').strip()
    notes = request.form.get('notes', '').strip()
    fit_rating = request.form.get('fit_rating', 'perfect')
    image_url = request.form.get('image_url', '').strip()

    if not brand_name or not category or not size_label:
        flash("Please fill in Brand, Category, and Size.", "danger")
        return redirect(url_for('closet.index'))

    item_create = ClosetItemCreate(
        brand_name=brand_name,
        category=category,
        size_label=size_label,
        fit_rating=fit_rating,
        notes=notes or None,
        image_url=image_url or None
    )
    ClosetService.add_item(db, current_user.id, item_create)
    flash(f"Added {brand_name} {category} to your wardrobe!", "success")
    return redirect(url_for('closet.index'))


@closet_bp.route('/delete/<uuid:item_id>', methods=['POST'])
@login_required
def delete(item_id):
    """Delete an item from the wardrobe."""
    success = ClosetService.delete_item(db, current_user.id, item_id)
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if success:
            return jsonify({"success": True, "message": "Item removed from wardrobe."})
        return jsonify({"success": False, "error": "Item not found."}), 404
    
    if success:
        flash("Item removed from wardrobe.", "info")
    else:
        flash("Item not found.", "warning")
    return redirect(url_for('closet.index'))
