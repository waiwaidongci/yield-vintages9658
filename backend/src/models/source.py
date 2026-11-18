from sqlalchemy import Column,Integer,String,JSON
from src.config.database import Base
class Period(Base):
 __tablename__='yield_periods'
 id=Column(Integer,primary_key=True); name=Column(String(120),unique=True); description=Column(String(250))
class Source(Base):
 __tablename__='yield_lots'
 id=Column(Integer,primary_key=True); natural_key=Column(String(120),unique=True); data=Column(JSON,nullable=False)
class Policy(Base):
 __tablename__='denominator_policies'
 id=Column(Integer,primary_key=True); version=Column(String(120),unique=True); data=Column(JSON,nullable=False)
