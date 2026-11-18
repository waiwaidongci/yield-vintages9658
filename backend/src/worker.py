import time,json,traceback
from pathlib import Path
import redis
from src.config.database import Base,engine,Session
from src.config.settings import REDIS_URL
from src.models import identity,source,run
from src.models.run import Run
from src.services.calculation import calculate
from src.services.formula_engine import FormulaTimeout,DEFAULT_BUDGET_SECONDS
from src.services.delivery import tick
Base.metadata.create_all(engine)
r=redis.Redis.from_url(REDIS_URL)
# 单条复杂公式核算的墙钟预算（秒）；超时即拒绝发布，普通固定口径核算不受影响
FORMULA_BUDGET=DEFAULT_BUDGET_SECONDS
while True:
 Path('/tmp/worker-heartbeat').write_text(str(time.time()))
 try:
  item=r.lpop('report-jobs')
  if item:
   with Session() as db:
    job=db.get(Run,int(item))
    # 幂等：重试消息若对应任务已不在排队态（完成/失败/运行中），直接跳过，绝不重复发布
    if job and job.status=='queued':
     job.status='running';db.commit()
     try:
      kind=job.snapshot.get('policy',{}).get('kind')
      # 复杂（三级自定义）口径注入20秒墙钟预算；超时在引擎内部抛 FormulaTimeout
      deadline=time.monotonic()+FORMULA_BUDGET if kind=='custom' else None
      # 三级结果在一次求值内全部产出：任一层失败即整体抛错，无部分发布
      job.result=calculate(job.snapshot['sources'],job.snapshot['policy'],deadline=deadline)
      job.status='completed';job.error=None
     except FormulaTimeout as exc:
      job.status='failed';job.error='核算超时：'+str(exc)
      traceback.print_exc()
     except Exception as exc:
      job.status='failed';job.error='核算拒绝：'+str(exc)
      traceback.print_exc()
     db.commit()
  with Session() as db: tick(db)
 except Exception: traceback.print_exc()
 time.sleep(1)
