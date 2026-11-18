import time
from collections import defaultdict,deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
class RateLimit(BaseHTTPMiddleware):
 def __init__(self,app): super().__init__(app);self.visits=defaultdict(deque)
 async def dispatch(self,request,call_next):
  if request.url.path=='/health': return await call_next(request)
  key=request.client.host if request.client else 'local';q=self.visits[key];now=time.monotonic()
  while q and now-q[0]>60: q.popleft()
  if len(q)>=360: return JSONResponse({'detail':'请求过于频繁，请稍后重试'},429)
  q.append(now);return await call_next(request)
