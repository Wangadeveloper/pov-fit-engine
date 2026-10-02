import os
import glob
import re

services_dir = 'app/services'

for filepath in glob.glob(os.path.join(services_dir, '*.py')):
    if os.path.basename(filepath) == '__init__.py':
        continue
        
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Remove async/await
    content = content.replace('async def ', 'def ')
    content = content.replace('await ', '')
    
    # Replace AsyncSession
    content = content.replace('from sqlalchemy.ext.asyncio import AsyncSession', '')
    content = content.replace('db: AsyncSession', 'db')
    
    # DB calls
    content = content.replace('db.commit()', 'db.session.commit()')
    content = content.replace('db.refresh(', 'db.session.refresh(')
    content = content.replace('db.add(', 'db.session.add(')
    content = content.replace('db.delete(', 'db.session.delete(')
    
    # Basic execute select replacements. (This won't be perfect but gets us close)
    # result = db.execute(stmt) -> result = db.session.execute(stmt)
    content = content.replace('db.execute(', 'db.session.execute(')
    
    with open(filepath, 'w') as f:
        f.write(content)

print("Services refactored from async to sync.")
