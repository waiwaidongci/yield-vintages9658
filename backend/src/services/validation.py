import math
from src.config.settings import CONFIG
def number(value,name,minimum=0,integer=False):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum or (integer and int(value)!=value): raise ValueError(name+'数值不合法')
 return value
def validate_source(d):
 if not isinstance(d,dict) or set(d)!=set(CONFIG['fields']): raise ValueError('底稿字段必须与业务字段一致')
 for key in ('period','department'):
  if not isinstance(d[key],str) or not 1<=len(d[key])<=100: raise ValueError(key+'不能为空或过长')
 for k in ('input','first_pass','reworked_good','scrap'):number(d[k],k,integer=True)
 if d['input']<=0 or d['first_pass']+d['reworked_good']+d['scrap']!=d['input']:raise ValueError('投入必须大于0且一次通过+返工合格+报废应等于投入')
 if not isinstance(d['shift'],str) or not d['shift']:raise ValueError('班次不能为空')
def validate_policy(d):
 if not isinstance(d,dict) or not isinstance(d.get('version'),str) or not 2<=len(d['version'])<=120: raise ValueError('口径版本名不合法')
 if d.get('numerator') not in ('first_pass','total_good') or d.get('denominator') not in ('input','non_scrap'):raise ValueError('分子分母口径无效')
 if not isinstance(d.get('description'),str):raise ValueError('必须填写口径说明')
