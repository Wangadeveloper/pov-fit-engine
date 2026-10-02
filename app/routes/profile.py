import os
import uuid
from flask import Blueprint, render_template, request, jsonify, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.services.fit_service import FitService

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@profile_bp.route('/')
@login_required
def index():
    profile = FitService.get_or_create_profile(db, current_user.id)
    return render_template('profile/index.html', profile=profile)


@profile_bp.route('/api/upload-photo', methods=['POST'])
@login_required
def api_upload_photo():
    """
    Accepts a multipart file upload OR a JSON photo_url.
    Saves the file to static/uploads/tryon_photos/ and stores the URL in the fit profile.
    """
    # ── Case 1: file upload ──────────────────────────────────────────────────
    if 'photo' in request.files:
        file = request.files['photo']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected."}), 400
        if not _allowed_file(file.filename):
            return jsonify({"success": False, "error": "Invalid file type. Please upload a JPG, PNG, or WebP image."}), 400

        # Read into memory to check size
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return jsonify({"success": False, "error": "File too large (max 10 MB)."}), 400

        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'tryon_photos')
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(file_bytes)

        # Build a URL the frontend can use
        photo_url = url_for('static', filename=f'uploads/tryon_photos/{filename}', _external=True)

        profile = FitService.get_or_create_profile(db, current_user.id)
        profile.try_on_photo_url = photo_url
        db.session.commit()

        return jsonify({
            "success": True,
            "photo_url": photo_url,
            "message": "Photo uploaded! Virtual Try-On is now ready.",
        })

    # ── Case 2: JSON URL (legacy / fallback) ────────────────────────────────
    data = request.get_json() or {}
    photo_url = data.get('photo_url', '').strip()
    if not photo_url:
        return jsonify({"success": False, "error": "No photo or URL provided."}), 400

    profile = FitService.get_or_create_profile(db, current_user.id)
    profile.try_on_photo_url = photo_url
    db.session.commit()

    return jsonify({
        "success": True,
        "photo_url": photo_url,
        "message": "Photo URL saved. Virtual Try-On is now ready.",
    })
