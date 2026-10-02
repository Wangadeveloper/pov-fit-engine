from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.closet import ClosetItem
from app.services.closet_service import ClosetService

closet_bp = Blueprint('closet', __name__, url_prefix='/closet')

@closet_bp.route('/')
@login_required
def index():
    # Use ClosetService
    items = ClosetService.get_user_closet(db, current_user.id)
    return render_template('closet/index.html', items=items)

@closet_bp.route('/add', methods=['POST'])
@login_required
def add():
    # Example logic using service
    pass
