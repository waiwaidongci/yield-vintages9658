# 002 三级自定义口径

## 背景

原口径仅支持固定分子/分母（`numerator`/`denominator` 四选二），多层分析需手算。本次新增逐批(lot)/线内(line)/全厂(plant)三级自定义口径，支持命名中间量、四则、IF 条件与低层向高层 SUM 聚合。

## 存储兼容性

- **无表结构变更、无数据回填**：自定义口径仍写入既有 `denominator_policies.data` JSON 列，以 `kind="custom"` 与旧固定口径区分；旧记录无 `kind` 字段，读取与核算走兼容路径。
- `yield_runs.snapshot` 仍在提交时冻结整套 `{policy, sources, period}` 并保存 SHA256；自定义口径的三级定义随快照整体冻结，后续改口径不影响排队/历史报告。
- 自定义核算结果在既有 `summary`/`rows` 之外新增 `lot_rows`/`line_rows`/`plant_rows`/`kind` 键；`rows` 仍指向线内透视，CSV 导出与旧报告读取不受影响。

## 口径 JSON 形态

```json
{
  "version": "三级自定义-一次通过良率-v1",
  "kind": "custom",
  "description": "...",
  "levels": {
    "lot":   [{"name": "净投入", "expr": "input - scrap", "type": "count"}],
    "line":  [{"name": "线净投入", "expr": "SUM(净投入)", "type": "count"}],
    "plant": [{"name": "全厂良率", "expr": "IF(SUM(厂净投入)>0, SUM(厂合格)/SUM(厂净投入), 0)", "type": "ratio"}]
  }
}
```

- `type` 仅 `count`(件数) / `ratio`(比例)；底稿字段 `input/first_pass/reworked_good/scrap` 均为 count。
- 分组维度：逐批=日期×试制线×班次（每条底稿一组）；线内=日期×试制线；全厂=日期。

## 校验纪律（登记与试算同一套，后端 `formula_engine.validate_custom_policy`）

1. 件数与比例不可相加/减；比较两端须同量纲；IF 两分支须同型；乘法仅允许 件数×比例；除法 count/count 得比例。
2. 高层不可直接取底稿字段（越级取值）；下层中间量只能出现在 `SUM()` 内；SUM 仅引用相邻下层或本层已聚合量。
3. 同层依赖做 DFS 环检测（含自引用），循环引用拒绝。
4. 未选中的 IF 分支运行期不求值（惰性）；零分母须用 IF 兜底，否则运行期报错。
5. 全厂层至少一个 ratio 型产出；中间量名不可与底稿字段冲突、同层不可重名。

## 运行与发布

- 复杂（custom）核算由 worker 注入 20 秒墙钟预算（`DEFAULT_BUDGET_SECONDS`），超时在引擎内抛 `FormulaTimeout`，任务置 `failed` 并写明原因、释放计算；同队列普通固定口径核算不带预算、照常推进。
- 三级结果在一次求值内全部产出，任一层失败整体抛错，**无部分发布**。
- worker 仅处理 `queued` 态任务；重试消息命中 `running/completed/failed` 直接跳过，失败重试不重复发布。
- 页面状态：queued 待校验 → running 计算中 → completed 完成 / failed（含原因）；旧口径报告继续可读、可导出、可被定时交付引用。

## 升级步骤

无需 SQL 迁移。重新构建 backend/worker/frontend 镜像后重启即可；已有自定义口径由 `scripts/seed_demo.py` 幂等补充一个示例版本，不覆盖任何用户数据。
