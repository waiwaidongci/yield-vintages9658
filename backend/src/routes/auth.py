from fastapi import APIRouter,Depends,HTTPException
from src.config.database import database
from src.models.identity import User
from src.schemas.requests import Login
from src.utils.security import password_ok,token
router=APIRouter()
@router.post('/auth/login')
def login(body:Login,db=Depends(database)):
 user=db.query(User).filter_by(email=body.email).first()
 if not user or not password_ok(body.password,user.password): raise HTTPException(401,'邮箱或密码错误')
 return {'token':token(user),'email':user.email,'role':user.role}
