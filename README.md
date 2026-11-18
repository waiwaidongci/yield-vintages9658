# 砚泉试制良率口径簿

试制批次一次通过/返工/报废→冻结口径版本与加权透视→主管复核交付；历史快照不随口径改写

## 业务场景与工作流
模拟客户：砚泉研究协作组，12位业务与分析人员。每月研究明细先从`yield-vintages-202611.csv`录入底稿，经口径冻结、Python核算、负责人复核后向业务阅读者交付站内CSV。原有流程依靠人工表格抄算，痛点为口径版本难追溯、重复计算易错、复核与交付脱节。

模块：业务总览、业务底稿、新建口径版本、异步核算与复核、定时交付、站内收件箱、审计。底稿可新增/修改/删除；口径仅新增版本；报告提交时冻结来源与版本并保存SHA256。定时交付引用已复核报告快照，worker到期写入数据库，业务阅读者下载。

## 三级自定义口径

在固定分子/分母口径之外，新增逐批(lot)/线内(line)/全厂(plant)三级自定义口径（`kind="custom"`），旧固定口径与历史报告完全保留：

- **命名中间量 + 四则 + 条件**：每级可定义若干中间量（`name/expr/type`），公式支持 `+ - * /`、括号、比较与 `IF(条件, 成立, 不成立)`；未选中的 IF 分支不计算。
- **低层向高层求和**：线内/全厂通过 `SUM(下层中间量)` 聚合相邻下级；分组维度为 逐批=日期×线×班次、线内=日期×线、全厂=日期。
- **量纲与引用纪律**：件数(count)与比例(ratio)不可相加；比较须同类、IF 分支同型；循环引用（含自引用）、越级取底稿字段、SUM 越级或直接取下层量，登记时一律拒绝。
- **页面可编辑并试算**：口径页三级表格在线编辑，`POST /policies/trial` 用当前底稿即时试算（不落库）；只有通过后端同一套校验的口径才能登记并用于报告。
- **冻结与发布**：提交即冻结整套口径定义与底稿（JSON 快照+SHA256），并发改口径不影响排队报告；三级结果一次求值、全部成功才一起发布，任一层失败无部分发布。
- **20秒预算**：复杂公式核算墙钟限 20 秒，超时拒绝发布并释放资源，同队列普通固定口径核算照常推进；worker 仅处理排队态任务，失败重试不重复发布。页面展示 待校验(queued)→计算中(running)→完成/失败及原因；旧口径报告仍可读取、导出与定时交付。

算法实现在`backend/src/services/formula_engine.py`（解析/类型推断/三级求值）与`calculation.py`（分发），输入校验在`validation.py`，试算服务在`trial.py`。


## 算法口径
版本化良率分母规则、加权汇总与按线/班次差异归因。分母规则手算；大批小批汇总不能均值；更新规则旧run不变。

口径版本冻结 · 汇总按分母加权。输入：业务底稿与口径JSON；输出：summary、透视rows、method、warnings。算法实现在`backend/src/services/calculation.py`，输入校验在`validation.py`。固定seed=42，240条合成数据；未对接真实业务系统。修改源数据和新建因子/口径不会改变已提交报告。

## 一天的验收剧本
1. 09:00 admin查看240条seed底稿与具名业务期间。
2. 09:10 analyst添加`yield-vintages-202611.csv`的一条具名业务记录。
3. 09:20 admin在口径版本页登记新版本；旧版本保留。
4. 09:30 analyst命名“十一月核算”并选择期间/版本排队。
5. 09:31 Redis worker真实执行Python计算，展示汇总/透视与口径边界。
6. 09:40 admin核对数值后填写至少4字复核说明。
7. 09:45 admin建立60秒周期计划，worker到期生成站内持久化交付。
8. 09:46 viewer在站内收件箱下载交付CSV；审计页查看操作者与时间。

## 快速启动
```sh
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```
前端 http://localhost:18253 ，后端 http://localhost:19253/docs ，数据库宿主端口17753。中文父目录可用。恰好5服务frontend/backend/worker/db/redis；均有真实healthcheck。停止并清空演示数据：`docker compose down -v --remove-orphans`。

|角色|邮箱|密码|权限|
|---|---|---|---|
|admin|admin@demo.local|Demo2026!|全部底稿、口径版本、核算、复核、调度|
|analyst|analyst@demo.local|Demo2026!|底稿增改删、核算、导出；无复核/调度/口径写权限|
|viewer|viewer@demo.local|Demo2026!|只读；仅可下载已复核报告与站内交付|

## 工程结构与开发
Python3.11/FastAPI/SQLAlchemy/Redis，MySQL8；前端原生HTML/CSS/JS ES modules，Nginx代理`/api/`剥前缀至后端。`frontend/src`按api/stores/pages/components/hooks/utils/router/constants/types拆分；`backend/src`按models/schemas/services/controllers/routes/middlewares/config/utils/constants拆分；`backend/scripts/seed_demo.py`自然键幂等且不覆盖用户修改。SQLAlchemy启动创建初始结构，迁移说明在backend/migrations。

后端开发：在backend安装requirements，设置DATABASE_URL/REDIS_URL/JWT_SECRET，`uvicorn src.main:app --reload`；前端可用Nginx或带同等代理的静态开发服务器。前后端全部业务计算在Python。

环境变量：COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、JWT_SECRET（部署替换）、DATABASE_URL、REDIS_URL、SEED_DEMO。`.env`不入Git。数据库/Redis/共享产物为命名卷。共享角色枚举admin/analyst/viewer与状态queued/running/completed/failed分别定义于backend/src/constants/enums.py和frontend/src/constants/enums.js。两个中间件：统一可恢复校验错误、每IP每分钟360请求限流。

## 已知边界
定时分发为站内收件箱；一名worker轮询执行，无外部邮件。调度发送已复核固定报告快照，不自动重算新数据。时间显示Asia/Shanghai。报告导出适合小型数据；底稿全量加载240行演示数据。Google Fonts不可用时回退serif。后端API以专属字段对象收发，页面通过业务输入控件编辑，不要求用户写JSON。新增来源期间自动可选；专属字段和算法严格校验。JWT演示有效期2小时。

MIT License。

## 实际实体映射
来源记录（Source，专属业务字段校验）、口径版本（Policy）、核算报告（Run）、交付计划（Schedule）、交付（Delivery）均经数据库→模型→请求schema→service→route/controller→frontend API→store→page。Period为已有来源期间字典，在任务期间选择器使用；不单独作为复杂度计数。底稿JSON为小型多字段单记录存储，不虚构未落库的子实体。

实际表：期间字典 yield_periods；专属来源 yield_lots；冻结口径 denominator_policies；异步报告 yield_runs。
