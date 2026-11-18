from collections import defaultdict
from src.services.validation import validate_source,validate_policy
def calculate(sources,policy):
 validate_policy(policy);pivot=defaultdict(lambda:[0,0,0]);rows=[]
 for s in sources:
  validate_source(s);num=s['first_pass'] if policy['numerator']=='first_pass' else s['first_pass']+s['reworked_good'];den=s['input'] if policy['denominator']=='input' else s['input']-s['scrap']
  if den<=0:raise ValueError('口径分母为0：'+s['department']+' '+s['period'])
  k=(s['period'],s['department'],s['shift']);p=pivot[k];p[0]+=num;p[1]+=den;p[2]+=1
 for (period,dept,shift),(num,den,count) in sorted(pivot.items()):rows.append({'日期':period,'试制线':dept,'班次':shift,'批数':count,'分子合计':num,'分母合计':den,'良率':num/den})
 n=sum(p[0] for p in pivot.values());d=sum(p[1] for p in pivot.values())
 return {'summary':{'批次数':len(sources),'分子合计':n,'分母合计':d,'加权良率':n/d if d else 0,'口径版本':policy['version']},'rows':rows,'method':'逐批按冻结版本选取分子/分母，再按日期×试制线×班次累加。汇总率=分子总数/分母总数，不对批次率做简单平均。可选口径仅为一次通过/总合格与全部投入/扣报废投入。','warnings':['扣报废分母会提升显示良率；比较不同版本时必须同时阅读分子与分母定义。']}
