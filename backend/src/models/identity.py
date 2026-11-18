from sqlalchemy import Column,Integer,String,JSON,Float,Text
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True); email=Column(String(120),unique=True); role=Column(String(20)); password=Column(String(250))
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True); actor=Column(String(120)); action=Column(String(80)); detail=Column(Text); at=Column(Float)
