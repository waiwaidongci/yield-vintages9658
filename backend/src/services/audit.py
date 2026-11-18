import time
from src.models.identity import Audit
def log(db,actor,action,detail):
 db.add(Audit(actor=actor,action=action,detail=str(detail),at=time.time()))
