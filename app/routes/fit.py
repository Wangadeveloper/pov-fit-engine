from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.services.fit_service import FitService

fit_bp = Blueprint('fit', __name__, url_prefix='/fit')


@fit_bp.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    profile = FitService.get_or_create_profile(db, current_user.id)

    if request.method == 'POST':
        from app.schemas.fit import OnboardingDetails
        try:
            data = OnboardingDetails(
                preferred_top_fit=request.form.get('preferred_top_fit', 'regular'),
                preferred_bottom_fit=request.form.get('preferred_bottom_fit', 'straight'),
                preferred_jacket_fit=request.form.get('preferred_jacket_fit', 'regular'),
                comfort_preferences=request.form.getlist('comfort_preferences'),
                height_cm=float(request.form['height_cm']) if request.form.get('height_cm') else None,
                weight_kg=float(request.form['weight_kg']) if request.form.get('weight_kg') else None,
            )
            FitService.save_onboarding(db, current_user.id, data)
            flash('Your fit profile has been updated!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            flash(f'Error saving profile: {e}', 'danger')

    return render_template('fit/onboarding.html', profile=profile)


@fit_bp.route('/')
@login_required
def index():
    profile = FitService.get_or_create_profile(db, current_user.id)
    return render_template('fit/index.html', profile=profile)


@fit_bp.route('/api/update-photo', methods=['POST'])
@login_required
def api_update_photo():
    """Legacy endpoint — delegates to profile.api_upload_photo."""
    from app.routes.profile import api_upload_photo
    return api_upload_photo()
