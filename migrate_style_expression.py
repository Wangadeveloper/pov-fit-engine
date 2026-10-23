"""
One-off migration: adds the `style_expression` column to fit_profiles.
Run with:  venv/bin/python3 migrate_style_expression.py
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("fit_profiles")]
    if "style_expression" in cols:
        print("Column style_expression already exists — nothing to do.")
    else:
        db.session.execute(
            text("ALTER TABLE fit_profiles ADD COLUMN style_expression VARCHAR(50)")
        )
        db.session.commit()
        print("✓ Migration complete: style_expression column added to fit_profiles.")
