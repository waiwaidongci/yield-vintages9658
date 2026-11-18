import base64,hashlib,hmac,json,time,secrets
from src.config.settings import SECRET
def password_hash(password,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),120000).hex()
def password_ok(password,encoded): return hmac.compare_digest(password_hash(password,encoded.split(':')[0]),encoded)
def b64(b): return base64.urlsafe_b64encode(b).decode().rstrip('=')
def token(user):
 header=b64(b'{"alg":"HS256","typ":"JWT"}');payload=b64(json.dumps({'sub':user.email,'role':user.role,'exp':int(time.time())+7200}).encode());body=header+'.'+payload
 return body+'.'+b64(hmac.new(SECRET.encode(),body.encode(),hashlib.sha256).digest())
def decode(value):
 header,payload,signature=value.split('.');body=header+'.'+payload
 if not hmac.compare_digest(signature,b64(hmac.new(SECRET.encode(),body.encode(),hashlib.sha256).digest())): raise ValueError('签名无效')
 obj=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
 if obj['exp']<time.time(): raise ValueError('登录过期')
 return obj
