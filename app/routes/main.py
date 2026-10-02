from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import select, func
from app.extensions import db
from app.models.closet import ClosetItem
from app.services.fit_service import FitService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    profile = FitService.get_or_create_profile(db, current_user.id)
    closet_count = db.session.execute(
        select(func.count(ClosetItem.id)).where(ClosetItem.user_id == current_user.id)
    ).scalar() or 0
    return render_template('dashboard/index.html', profile=profile, closet_count=closet_count)
