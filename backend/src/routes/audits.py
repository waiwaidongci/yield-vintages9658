from fastapi import APIRouter,Depends
from src.config.database import database
from src.controllers.auth import current
from src.models.identity import Audit
from src.utils.serialize import row
router=APIRouter()
@router.get('/audits')
def audits(db=Depends(database),u=Depends(current)): return [row(x) for x in db.query(Audit).order_by(Audit.id.desc()).limit(200).all()]
