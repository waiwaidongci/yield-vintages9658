"""三级自定义良率口径引擎。

支持：
- 逐批(lot)/线内(line)/全厂(plant)三级口径，层级 lot < line < plant；
- 命名中间量、四则运算(+ - * / 与括号)、条件分支 IF(cond, a, b) 与比较；
- 低层向高层求和 SUM(中间量)，仅允许相邻下一级；
- 类型纪律：件数(count)与比例(ratio)不可相加，比较仅同类，条件两分支同型；
- 循环引用检测、越级取值拒绝；未选中的条件分支不求值；
- 复杂公式 20 秒预算，超时拒绝并由调用方释放资源。

口径 JSON 结构（kind='custom'）::

    {"version": "...", "kind": "custom", "description": "...",
     "levels": {
       "lot":   [{"name": "投入", "expr": "input", "type": "count"}, ...],
       "line":  [{"name": "线良率", "expr": "SUM(合格数) / SUM(投入)", "type": "ratio"}, ...],
       "plant": [{"name": "厂良率", "expr": "IF(SUM(线投入) > 0, SUM(线合格) / SUM(线投入), 0)", "type": "ratio"}]
     }}

旧版固定口径（numerator/denominator）仍由 calculation.py 的兼容路径处理。
"""
import ast
import math
import time

LEVELS = ('lot', 'line', 'plant')
LEVEL_LABEL = {'lot': '逐批', 'line': '线内', 'plant': '全厂'}
_TYPES = ('count', 'ratio')
_TYPE_LABEL = {'count': '件数', 'ratio': '比例'}
# 底稿原始字段及其数值类型
FIELD_TYPES = {
    'input': 'count',
    'first_pass': 'count',
    'reworked_good': 'count',
    'scrap': 'count',
}
# 各级分组维度（逐级汇总）；逐批层每条底稿自成一组，不参与 SUM
GROUP_KEYS = {
    'lot': ('日期', '试制线', '班次'),
    'line': ('日期', '试制线'),
    'plant': ('日期',),
}
DEFAULT_BUDGET_SECONDS = 20.0
_NAME_MAX = 40
_EXPR_MAX = 400


class FormulaError(ValueError):
    """口径定义或求值错误（消息直接面向页面）。"""


class FormulaTimeout(FormulaError):
    """复杂公式核算超过时间预算。"""


# ---------------------------------------------------------------- 静态校验

def _check_name(name, taken, level):
    if not isinstance(name, str) or not name.strip():
        raise FormulaError(f'{LEVEL_LABEL[level]}层存在未命名的中间量')
    name = name.strip()
    if len(name) > _NAME_MAX:
        raise FormulaError(f'中间量名“{name}”超过{_NAME_MAX}字')
    if name in FIELD_TYPES:
        raise FormulaError(f'中间量名“{name}”与底稿字段冲突，请换名')
    if name in taken:
        raise FormulaError(f'{LEVEL_LABEL[level]}层中间量“{name}”重复定义')
    if not all(ord(ch) > 127 or ch.isalnum() or ch == '_' for ch in name) or name[0].isdigit():
        raise FormulaError(f'中间量名“{name}”只能用中文、字母、数字、下划线且不以数字开头')
    return name


def _collect_names(tree):
    """收集表达式内全部 Name 与 Call 函数名。"""
    names, calls = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Call):
            calls.append(node.func.id if isinstance(node.func, ast.Name) else None)
    return names, calls


def _validate_expr(expr, level, idx, known_vars, var_types, lower_vars):
    """语法 + 引用 + 类型推断，返回表达式推断类型。"""
    if not isinstance(expr, str) or not expr.strip():
        raise FormulaError(f'{LEVEL_LABEL[level]}层第{idx + 1}个中间量缺少公式')
    if len(expr) > _EXPR_MAX:
        raise FormulaError(f'{LEVEL_LABEL[level]}层公式超过{_EXPR_MAX}字符')
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as exc:
        raise FormulaError(f'{LEVEL_LABEL[level]}层公式“{expr}”语法错误：{exc.msg}')
    names, calls = _collect_names(tree)
    for call in calls:
        if call not in ('SUM', 'IF'):
            raise FormulaError(f'{LEVEL_LABEL[level]}层公式仅支持 SUM、IF 函数，发现 {call}')
    # 下层中间量只允许出现在 SUM(...) 的直接参数位置
    sum_args = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'SUM':
            if len(node.args) == 1 and isinstance(node.args[0], ast.Name):
                sum_args.add(node.args[0].id)
    lower_level = LEVELS[LEVELS.index(level) - 1] if level != 'lot' else None
    for token in names:
        if token in ('SUM', 'IF'):
            continue
        if token in FIELD_TYPES:
            if level != 'lot':
                raise FormulaError(
                    f'{LEVEL_LABEL[level]}层越级取值：底稿字段“{token}”只能在逐批层使用，'
                    f'高层请用 SUM 引用{LEVEL_LABEL[lower_level]}层中间量')
            continue
        if token in lower_vars and token not in sum_args:
            raise FormulaError(
                f'{LEVEL_LABEL[level]}层越级取值：“{token}”是{LEVEL_LABEL[lower_level]}层'
                f'的下级中间量，只能在 SUM() 内引用，不可直接取值')
        if token not in known_vars and token not in lower_vars:
            raise FormulaError(f'{LEVEL_LABEL[level]}层公式引用了未定义的量“{token}”（同层中间量须先定义后引用）')
    return _infer_type(tree, level, var_types, lower_vars)


def _infer_type(tree, level, var_types, lower_vars):
    def typ(node):
        if isinstance(node, ast.Expression):
            return typ(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise FormulaError('公式只允许数字常量')
            if not math.isfinite(node.value):
                raise FormulaError('公式常量必须是有限数')
            # 字面量 0 为中性值：可作件数零或比例零（IF 兜底常用）；非零常量按件数
            return 'num0' if node.value == 0 else 'count'
        if isinstance(node, ast.Name):
            if node.id in FIELD_TYPES:
                return FIELD_TYPES[node.id]
            return var_types[node.id]
        if isinstance(node, ast.BinOp):
            lt, rt = typ(node.left), typ(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                ut = _unify(lt, rt)
                if ut is None:
                    raise FormulaError(
                        f'拒绝{_TYPE_LABEL[lt]}与{_TYPE_LABEL[rt]}相'
                        f'{"加" if isinstance(node.op, ast.Add) else "减"}：比例与件数量纲不同')
                return ut
            if isinstance(node.op, ast.Mult):
                # count * ratio 允许（如 件数×占比），count*count 与 ratio*ratio 拒绝；
                # 中性 0 参与乘法时统一为另一操作数类型
                if 'num0' in (lt, rt):
                    return _unify(lt, rt)
                if lt == rt:
                    raise FormulaError(f'不允许 {_TYPE_LABEL[lt]}×{_TYPE_LABEL[rt]}，乘法仅支持件数×比例')
                return 'count'
            if isinstance(node.op, ast.Div):
                # 除数/被除量须为件数（比例零可作中性零参与），count / count -> ratio
                if lt == 'ratio' or rt == 'ratio':
                    raise FormulaError('比例不可参与除法分子分母之外的复合运算（除数/被除量须为件数）')
                return 'ratio'
            raise FormulaError('不支持的运算符')
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.USub, ast.UAdd)):
                raise FormulaError('不支持的一元运算')
            return typ(node.operand)
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or not isinstance(
                node.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)):
                raise FormulaError('比较仅支持单个 >、>=、<、<=、=、<>')
            lt, rt = typ(node.left), typ(node.comparators[0])
            if _unify(lt, rt) is None:
                raise FormulaError(f'比较两端量纲必须相同，发现 {_TYPE_LABEL[lt]} 与 {_TYPE_LABEL[rt]}')
            return 'bool'
        if isinstance(node, ast.Call):
            if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
                raise FormulaError('函数不支持关键字或展开参数')
            if node.func.id == 'IF':
                if len(node.args) != 3:
                    raise FormulaError('IF 需要三个参数：IF(条件, 成立值, 不成立值)')
                ct = typ(node.args[0])
                if ct != 'bool':
                    raise FormulaError('IF 第一个参数必须是比较条件')
                at, bt = typ(node.args[1]), typ(node.args[2])
                ut = _unify(at, bt)
                if ut is None:
                    raise FormulaError('IF 两个分支类型必须一致（同为件数或同为比例）')
                return ut
            if node.func.id == 'SUM':
                if level == 'lot':
                    raise FormulaError('逐批层为最底层，不能使用 SUM')
                if len(node.args) != 1 or not isinstance(node.args[0], ast.Name):
                    raise FormulaError('SUM 仅接受单个下层或同层中间量引用，如 SUM(合格数)')
                token = node.args[0].id
                if token in var_types:
                    return var_types[token]  # 同层已聚合量（如本层先 SUM 出计数再相除）
                if token not in lower_vars:
                    raise FormulaError(
                        f'SUM 只能引用{LEVEL_LABEL[LEVELS[LEVELS.index(level) - 1]]}层中间量，“{token}”不在该层')
                return lower_vars[token]
            raise FormulaError('不支持的函数')
        if isinstance(node, ast.BoolOp):
            raise FormulaError('不支持 and/or，请用嵌套 IF 表达条件')
        raise FormulaError('公式含不支持的语法')

    return typ(tree)


def _unify(a, b):
    """两类统一：中性零(num0)随另一类；件数与比例互斥。返回 None 表示量纲冲突。"""
    if a == b:
        return 'count' if a == 'num0' else a
    if a == 'num0':
        return b
    if b == 'num0':
        return a
    return None


def validate_custom_policy(policy):
    """完整静态校验自定义口径；返回规范化后的 levels 结构。"""
    if not isinstance(policy, dict):
        raise FormulaError('口径定义必须是对象')
    version = policy.get('version')
    if not isinstance(version, str) or not 2 <= len(version) <= 120:
        raise FormulaError('口径版本名不合法')
    if not isinstance(policy.get('description'), str) or not policy['description'].strip():
        raise FormulaError('必须填写口径说明')
    levels = policy.get('levels')
    if not isinstance(levels, dict) or not all(k in levels for k in LEVELS):
        raise FormulaError('口径必须同时包含逐批、线内、全厂三级定义')
    normalized = {}
    lower_vars = {}
    for level in LEVELS:
        defs = levels[level]
        if not isinstance(defs, list) or not defs:
            raise FormulaError(f'{LEVEL_LABEL[level]}层至少定义一个中间量')
        if len(defs) > 50:
            raise FormulaError(f'{LEVEL_LABEL[level]}层中间量不可超过50个')
        # 第一遍：收集本层全部名称与声明类型（允许同层前向引用，循环由后续 DFS 拦截）
        raw = []
        known, vtypes = {}, {}
        for idx, item in enumerate(defs):
            if not isinstance(item, dict) or set(item) != {'name', 'expr', 'type'}:
                raise FormulaError(f'{LEVEL_LABEL[level]}层中间量须含 name/expr/type 三个字段')
            name = _check_name(item['name'], known, level)
            if item['type'] not in _TYPES:
                raise FormulaError(f'中间量“{name}”类型必须是 count(件数) 或 ratio(比例)')
            if not isinstance(item['expr'], str) or not item['expr'].strip():
                raise FormulaError(f'{LEVEL_LABEL[level]}层中间量“{name}”缺少公式')
            known[name] = item['expr'].strip()
            vtypes[name] = item['type']
            raw.append({'name': name, 'expr': item['expr'].strip(), 'type': item['type']})
        # 第二遍：用完整的同层符号表做引用与类型推断
        ordered = []
        for idx, item in enumerate(raw):
            inferred = _validate_expr(item['expr'], level, idx, known, vtypes, lower_vars)
            if inferred == 'num0':
                inferred = 'count'  # 纯零表达式按件数登记
            if inferred != item['type']:
                raise FormulaError(
                    f'中间量“{item["name"]}”声明为{_TYPE_LABEL[item["type"]]}，'
                    f'但公式推断为{_TYPE_LABEL[inferred]}')
            ordered.append(item)
        # 依赖环检测（本层 Name 依赖，含自引用；SUM 依赖下层，下层不可反向引用故不可能成环）
        graph = {}
        for item in ordered:
            tree = ast.parse(item['expr'], mode='eval')
            graph[item['name']] = {
                n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in known
            }
        state = {}

        def visit(node):
            if state.get(node) == 1:
                raise FormulaError(f'{LEVEL_LABEL[level]}层存在循环引用，环经过“{node}”')
            if state.get(node) == 2:
                return
            state[node] = 1
            for nxt in graph[node]:
                visit(nxt)
            state[node] = 2

        for n in graph:
            visit(n)
        normalized[level] = ordered
        lower_vars = vtypes
    # 全厂层必须产出至少一个比例（良率口径的交付物）
    if not any(d['type'] == 'ratio' for d in normalized['plant']):
        raise FormulaError('全厂层至少需要一个比例(ratio)型结果作为良率产出')
    return {'version': version, 'kind': 'custom',
            'description': policy['description'].strip(), 'levels': normalized}


# ---------------------------------------------------------------- 运行期求值

class _Compiler:
    """把 AST 编译成闭包，严格按推断规则运算；IF 走惰性分支。"""

    def __init__(self, deadline, counter):
        self.deadline = deadline
        self.counter = counter  # [步数]

    def tick(self):
        self.counter[0] += 1
        if self.deadline and time.monotonic() > self.deadline:
            raise FormulaTimeout('复杂公式核算超过20秒，已拒绝发布并释放计算资源')

    def compile(self, node):
        self.tick()
        if isinstance(node, ast.Expression):
            return self.compile(node.body)
        if isinstance(node, ast.Constant):
            value = node.value
            return lambda ctx: value
        if isinstance(node, ast.Name):
            key = node.id
            return lambda ctx: ctx[key]
        if isinstance(node, ast.BinOp):
            lf, rf = self.compile(node.left), self.compile(node.right)
            op = type(node.op)
            if op is ast.Add:
                return lambda ctx: self._num(lf(ctx) + rf(ctx))
            if op is ast.Sub:
                return lambda ctx: self._num(lf(ctx) - rf(ctx))
            if op is ast.Mult:
                return lambda ctx: self._num(lf(ctx) * rf(ctx))
            if op is ast.Div:
                def div(ctx):
                    r = rf(ctx)
                    if r == 0:
                        raise FormulaError('除法分母为0，请用 IF 条件给零分母兜底')
                    return self._num(lf(ctx) / r)
                return div
        if isinstance(node, ast.UnaryOp):
            f = self.compile(node.operand)
            if isinstance(node.op, ast.USub):
                return lambda ctx: -f(ctx)
            return f
        if isinstance(node, ast.Compare):
            lf, rf = self.compile(node.left), self.compile(node.comparators[0])
            ops = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
                   ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
                   ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}
            check = ops[type(node.ops[0])]
            return lambda ctx: check(lf(ctx), rf(ctx))
        if isinstance(node, ast.Call):
            if node.func.id == 'IF':
                cond, when_true, when_false = (self.compile(a) for a in node.args)

                def branch(ctx):
                    # 未选中的分支不计算
                    return when_true(ctx) if cond(ctx) else when_false(ctx)

                return branch
            # SUM：值由上下文预聚合注入
            token = node.args[0].id
            return lambda ctx: ctx['__sum__'][token]
        raise FormulaError('公式含不支持的语法（应已在静态校验拦截）')

    @staticmethod
    def _num(value):
        if not math.isfinite(value):
            raise FormulaError('计算结果出现非有限数（溢出或除零）')
        return value


def _group_rows(rows, keys):
    buckets = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        buckets.setdefault(key, []).append(row)
    return buckets


def _topo_order(defs):
    """同层中间量按依赖拓扑排序（静态校验已保证无环），保证惰性闭包取值时依赖已入 ctx。"""
    names = {d['name'] for d in defs}
    graph = {}
    for d in defs:
        tree = ast.parse(d['expr'], mode='eval')
        graph[d['name']] = {n.id for n in ast.walk(tree)
                            if isinstance(n, ast.Name) and n.id in names}
    ordered, state = [], {}

    def visit(n):
        if state.get(n) == 2:
            return
        state[n] = 1
        for nxt in graph[n]:
            visit(nxt)
        state[n] = 2
        ordered.append(n)

    for d in defs:
        visit(d['name'])
    by_name = {d['name']: d for d in defs}
    return [by_name[n] for n in ordered]


def evaluate_custom(sources, policy, deadline=None, step_budget=None):
    """按三级口径求值。

    返回 {"summary":..., "rows":..., "line_rows":..., "plant_rows":...,
          "method":..., "warnings":...}，结构与旧 calculate() 兼容（含 summary/rows）。
    """
    levels = policy['levels']
    counter = [0]
    compiler = _Compiler(deadline, counter)

    def check_budget():
        # 运行期墙钟预算：每条底稿/每个分组求值前检查，超时立即拒绝（过冲不超过一组）
        if deadline is not None and time.monotonic() > deadline:
            raise FormulaTimeout('复杂公式核算超过20秒，已拒绝发布并释放计算资源')

    compiled = {lvl: [(d['name'], d['type'], compiler.compile(ast.parse(d['expr'], mode='eval')))
                      for d in _topo_order(levels[lvl])] for lvl in LEVELS}

    # ---- 逐批层：每条底稿独立求值
    lot_records = []
    for s in sources:
        check_budget()
        ctx = dict(s)  # 仅含底稿专属字段 input/first_pass/...
        record = {'日期': s['period'], '试制线': s['department'], '班次': s['shift']}
        for name, _typ, fn in compiled['lot']:
            ctx[name] = fn(ctx)
            record[name] = ctx[name]
        lot_records.append(record)

    def roll_up(target_level, child_records):
        """按目标层维度对子层展示记录分组，SUM 下层中间量后求本层表达式。"""
        keys = GROUP_KEYS[target_level]
        buckets = _group_rows(child_records, keys)
        out = []
        for key in sorted(buckets):
            check_budget()
            members = buckets[key]
            sums = {}
            lower_defs = levels[LEVELS[LEVELS.index(target_level) - 1]]
            for d in lower_defs:
                sums[d['name']] = sum(m.get(d['name'], 0) for m in members)
            ctx = {'__sum__': sums}
            display = {label: val for label, val in zip(keys, key)}
            for name, _typ, fn in compiled[target_level]:
                value = fn(ctx)
                ctx[name] = value
                # 同层中间量可被本层后续 SUM 引用（值即该分组的聚合结果）
                sums[name] = value
                display[name] = value
            out.append(display)
        return out

    line_rows = roll_up('line', lot_records)
    plant_rows = roll_up('plant', line_rows)

    if step_budget and counter[0] > step_budget:
        raise FormulaTimeout('公式步数超预算，已拒绝发布')

    # ---- 汇总：全厂层按周期合并；summary 取最后一个全厂良率型结果
    ratio_defs = [d['name'] for d in levels['plant'] if d['type'] == 'ratio']
    head = plant_rows[0] if plant_rows else {}
    summary = {
        '批次数': len(sources),
        '线内分组数': len(line_rows),
        '全厂分组数': len(plant_rows),
        '口径版本': policy['version'],
    }
    for name in ratio_defs:
        summary[f'全厂·{name}'] = head.get(name, 0)
    warnings = ['自定义口径已冻结：件数与比例不可混加；未选中条件分支不参与计算；'
                '高层数值均由低层 SUM 聚合，不做批次率简单平均。']
    method = ('三级口径：逐批层基于底稿字段计算命名中间量；线内/全厂层仅通过 SUM 聚合'
              '相邻下层中间量后再做四则与 IF 条件；越级取值、循环引用、件数加比例均在登记时拒绝。')
    return {
        'summary': summary,
        'rows': line_rows,          # 主透视表沿用 rows 键，保证 CSV 导出兼容
        'lot_rows': lot_records,
        'line_rows': line_rows,
        'plant_rows': plant_rows,
        'method': method,
        'warnings': warnings,
        'kind': 'custom',
    }
