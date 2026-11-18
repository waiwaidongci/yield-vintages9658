import json,random
from src.config.database import Base,engine,Session
from src.config.settings import CONFIG
from src.models.identity import User
from src.models.source import Source,Policy,Period
from src.models import run
from src.utils.security import password_hash
from src.services.validation import validate_source,validate_policy

def demo_rows():
 rng=random.Random(42);rows=[]
 for i in range(240):
  n=rng.randint(100,1200);fp=int(n*rng.uniform(.7,.96));rw=rng.randint(0,n-fp);rows.append({'period':'2026-11-'+str(1+i%20).zfill(2),'department':['试制线A','试制线B','试制线C'][i%3],'shift':['早班','晚班'][i%2],'input':n,'first_pass':fp,'reworked_good':rw,'scrap':n-fp-rw})
 return rows

# 三级自定义口径示例：逐批命名中间量 → 线内 SUM 聚合求线良率 → 全厂再聚合，零分母由 IF 兜底
CUSTOM_POLICY={
 'version':'三级自定义-一次通过良率-v1',
 'kind':'custom',
 'description':'逐批计算一次通过/总合格/净投入命名中间量；线内与全厂仅通过 SUM 低层中间量聚合，IF 兜底零分母，不做批次率平均。',
 'levels':{
  'lot':[
   {'name':'一次通过','expr':'first_pass','type':'count'},
   {'name':'返工合格','expr':'reworked_good','type':'count'},
   {'name':'总合格','expr':'first_pass + reworked_good','type':'count'},
   {'name':'净投入','expr':'input - scrap','type':'count'},
   {'name':'批一次通过率','expr':'IF(input > 0, first_pass / input, 0)','type':'ratio'},
  ],
  'line':[
   {'name':'线一次通过','expr':'SUM(一次通过)','type':'count'},
   {'name':'线总合格','expr':'SUM(总合格)','type':'count'},
   {'name':'线净投入','expr':'SUM(净投入)','type':'count'},
   {'name':'线一次通过良率','expr':'IF(SUM(净投入) > 0, SUM(一次通过) / SUM(净投入), 0)','type':'ratio'},
  ],
  'plant':[
   {'name':'厂一次通过','expr':'SUM(线一次通过)','type':'count'},
   {'name':'厂总合格','expr':'SUM(线总合格)','type':'count'},
   {'name':'厂净投入','expr':'SUM(线净投入)','type':'count'},
   {'name':'全厂一次通过良率','expr':'IF(SUM(厂净投入) > 0, SUM(厂一次通过) / SUM(厂净投入), 0)','type':'ratio'},
  ],
 }}

def seed():
 Base.metadata.create_all(engine)
 with Session() as db:
  for role in ('admin','analyst','viewer'):
   if not db.query(User).filter_by(email=role+'@demo.local').first():db.add(User(email=role+'@demo.local',role=role,password=password_hash('Demo2026!')))
  rows=demo_rows()
  for name in sorted(set(r['period'] for r in rows)):
   if not db.query(Period).filter_by(name=name).first():db.add(Period(name=name,description='合成演示业务期间，seed=42'))
  for i,data in enumerate(rows):
   validate_source(data);key='demo-'+str(i+1)
   if not db.query(Source).filter_by(natural_key=key).first():db.add(Source(natural_key=key,data=data))
  if not db.query(Policy).filter_by(version=CONFIG['policy']['version']).first():db.add(Policy(version=CONFIG['policy']['version'],data=CONFIG['policy']))
  if not db.query(Policy).filter_by(version=CUSTOM_POLICY['version']).first():
   validate_policy(CUSTOM_POLICY);db.add(Policy(version=CUSTOM_POLICY['version'],data=CUSTOM_POLICY))
  db.commit();print(json.dumps({'users':db.query(User).count(),'sources':db.query(Source).count(),'policies':db.query(Policy).count(),'periods':db.query(Period).count()},ensure_ascii=False))
if __name__=='__main__':seed()
