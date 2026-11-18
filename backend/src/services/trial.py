"""口径页面试算：不落库、不排队，用当前底稿对编辑中的口径即时求值。

试算同样经过完整静态校验与 20 秒预算；只有试算通过的口径才允许登记并用于报告。
"""
import time
from fastapi import HTTPException
from src.models.source import Source
from src.services.validation import validate_policy
from src.services.calculation import calculate
from src.services.formula_engine import FormulaTimeout, DEFAULT_BUDGET_SECONDS


def trial(db, body):
    policy = body.data
    try:
        validate_policy(policy)
    except ValueError as exc:
        raise HTTPException(422, f'口径校验未通过：{exc}')
    sources = [x.data for x in db.query(Source).order_by(Source.id).all()
               if body.period == '全部' or x.data.get('period') == body.period]
    if not sources:
        raise HTTPException(422, '所选期间没有底稿，无法试算')
    deadline = time.monotonic() + DEFAULT_BUDGET_SECONDS if policy.get('kind') == 'custom' else None
    try:
        result = calculate(sources, policy, deadline=deadline)
    except FormulaTimeout as exc:
        raise HTTPException(422, f'试算超时被拒绝：{exc}')
    except ValueError as exc:
        raise HTTPException(422, f'试算被拒绝：{exc}')
    return {'ok': True, 'result': result, 'validated': True}
