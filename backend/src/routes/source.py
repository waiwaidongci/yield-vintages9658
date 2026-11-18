from fastapi import APIRouter,Depends,HTTPException
from src.config.database import database
from src.controllers.auth import current,editor,admin
from src.models.source import Source,Policy,Period
from src.schemas.requests import DataInput
from src.services.source import save_source,save_policy
from src.services.audit import log
from src.utils.serialize import row
router=APIRouter()
@router.get('/sources')
def sources(db=Depends(database),u=Depends(current)): return [row(x) for x in db.query(Source).order_by(Source.id).all()]
@router.get('/periods')
def periods(db=Depends(database),u=Depends(current)):
 names=sorted({x.data['period'] for x in db.query(Source).all()})
 return [{'id':i+1,'name':name,'description':'当前来源期间'} for i,name in enumerate(names)]
@router.post('/sources')
def create(b:DataInput,db=Depends(database),u=Depends(editor)): return row(save_source(db,u,b.data))
@router.put('/sources/{id}')
def update(id:int,b:DataInput,db=Depends(database),u=Depends(editor)): return row(save_source(db,u,b.data,id))
@router.delete('/sources/{id}')
def delete(id:int,db=Depends(database),u=Depends(editor)):
 obj=db.get(Source,id)
 if not obj: raise HTTPException(404,'底稿不存在')
 db.delete(obj);log(db,u.email,'source.delete',id);db.commit();return {'deleted':id}
@router.get('/policies')
def policies(db=Depends(database),u=Depends(current)): return [row(x) for x in db.query(Policy).order_by(Policy.id).all()]
@router.post('/policies')
def policy(b:DataInput,db=Depends(database),u=Depends(admin)): return row(save_policy(db,u,b.data))
