from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from src.config.database import database
from src.controllers.auth import current,editor,admin
from src.models.run import Run
from src.schemas.requests import RunInput,ReviewInput
from src.services.report import submit,approve
from src.services.export import csv_text
from src.utils.serialize import row
router=APIRouter()
@router.get('/runs')
def runs(db=Depends(database),u=Depends(current)): return [row(x) for x in db.query(Run).order_by(Run.id.desc()).all()]
@router.post('/runs')
def create(b:RunInput,db=Depends(database),u=Depends(editor)): return row(submit(db,u,b))
@router.get('/runs/{id}')
def detail(id:int,db=Depends(database),u=Depends(current)):
 obj=db.get(Run,id)
 if not obj: raise HTTPException(404,'报告不存在')
 return row(obj)
@router.post('/runs/{id}/approve')
def review(id:int,b:ReviewInput,db=Depends(database),u=Depends(admin)): return row(approve(db,u,id,b.note))
@router.get('/runs/{id}/csv')
def download(id:int,db=Depends(database),u=Depends(current)):
 obj=db.get(Run,id)
 if not obj or obj.status!='completed': raise HTTPException(409,'报告尚未完成')
 if u.role=='viewer' and not obj.approved: raise HTTPException(403,'业务阅读者仅可下载已复核报告')
 return Response(csv_text(obj.result),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="report-{id}.csv"'})
