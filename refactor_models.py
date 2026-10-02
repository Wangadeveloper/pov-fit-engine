import os
import glob

models_dir = 'app/models'

for filepath in glob.glob(os.path.join(models_dir, '*.py')):
    if os.path.basename(filepath) == '__init__.py':
        continue
        
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Replace Base with db.Model
    content = content.replace('from app.core.database import Base', 'from app.extensions import db')
    content = content.replace('(Base):', '(db.Model):')
    
    # Handle User model specially for UserMixin
    if os.path.basename(filepath) == 'user.py':
        if 'UserMixin' not in content:
            content = content.replace('import uuid\n', 'import uuid\nfrom flask_login import UserMixin\n')
            content = content.replace('class User(db.Model):', 'class User(db.Model, UserMixin):')
            
    # Fix the uuid default, instead of using str(uuid.uuid4), usually it's better to leave it.
    # Flask-SQLAlchemy 3+ uses standard SQLAlchemy 2.0. Mapped is fully supported.
    
    with open(filepath, 'w') as f:
        f.write(content)

print("Models refactored.")
