from fastapi import HTTPException
from src.models.source import Source,Policy,Period
from src.services.validation import validate_source,validate_policy
from src.services.audit import log
import uuid
def save_source(db,user,data,id=None):
 validate_source(data)
 obj=db.get(Source,id) if id else Source(natural_key='user-'+uuid.uuid4().hex)
 if not obj: raise HTTPException(404,'底稿不存在')
 obj.data=data;db.add(obj)
 if not db.query(Period).filter_by(name=data['period']).first():db.add(Period(name=data['period'],description='业务来源自动登记期间'))
 log(db,user.email,'source.update' if id else 'source.create',obj.natural_key);db.commit();return obj
def save_policy(db,user,data):
 validate_policy(data)
 if db.query(Policy).filter_by(version=data['version']).first(): raise HTTPException(409,'版本名已存在，请另建版本保留历史')
 obj=Policy(version=data['version'],data=data);db.add(obj);log(db,user.email,'policy.version',data['version']);db.commit();return obj
