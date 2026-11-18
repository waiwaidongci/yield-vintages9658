from fastapi import Header,HTTPException,Depends
from src.utils.security import decode
from src.config.database import database
from src.models.identity import User
def current(authorization:str=Header(default=''),db=Depends(database)):
 try:
  claims=decode(authorization.removeprefix('Bearer '));user=db.query(User).filter_by(email=claims['sub']).first()
  if not user: raise ValueError('账号不存在')
  return user
 except Exception: raise HTTPException(401,'请重新登录')
def editor(user=Depends(current)):
 if user.role not in ('admin','analyst'): raise HTTPException(403,'仅负责人或分析师可以写入')
 return user
def admin(user=Depends(current)):
 if user.role!='admin': raise HTTPException(403,'仅负责人可以执行此动作')
 return user
