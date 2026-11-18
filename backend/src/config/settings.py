import os,json
from pathlib import Path
CONFIG=json.loads(Path('/app/project.json').read_text())
DATABASE_URL=os.environ['DATABASE_URL']
REDIS_URL=os.getenv('REDIS_URL','redis://redis:6379/0')
SECRET=os.environ['JWT_SECRET']
