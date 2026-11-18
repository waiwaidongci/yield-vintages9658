from pydantic import BaseModel,Field
class Login(BaseModel): email:str; password:str
class DataInput(BaseModel): data:dict
class RunInput(BaseModel): name:str=Field(min_length=2,max_length=120); policy_id:int; period:str='全部'
class ReviewInput(BaseModel): note:str=Field(min_length=4,max_length=2000)
class ScheduleInput(BaseModel): name:str=Field(min_length=2,max_length=120); run_id:int; interval_seconds:int=Field(ge=5,le=86400)
class TrialInput(BaseModel):
 data:dict=Field(description='页面编辑中的口径定义（自定义或固定口径）')
 period:str='全部'
