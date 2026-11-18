from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
class Errors(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  try: return await call_next(request)
  except ValueError as exc: return JSONResponse({'detail':str(exc)},status_code=422)
