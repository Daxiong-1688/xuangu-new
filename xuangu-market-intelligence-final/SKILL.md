---
name: xuangu-market-intelligence-final
description: "Run the production 玄谷 Yixin-driven market intelligence workflow: fetch the latest completed trading-day data, dynamically identify actual leading, lagging, strengthening and abnormal A-share sectors, explain price moves with evidence-constrained attribution, build a complete market map, conditional forecast and risk-gated three-layer stock pools, then deterministically render and validate the locked final three-page HTML console. Use for 大盘分析、市场地图、板块涨跌归因、资金迁移、热点生命周期、未来市场预测、三层股票池、风险排雷、每日玄谷控制台，或需要1:1复现最终市场研究HTML时。"
---

# 玄谷市场研究生产工作流

执行最终研究方法，不重演历史调优。把AI用于证据约束的归因和预测，把取数、计算、Bundle合并、UI渲染与验收交给固定脚本。

## 强制边界

1. 只使用Yixin Search与Fin DB；Search和Fin DB读取各自绑定的密钥。
2. 每次调用Yixin重新解析最新完成交易日；禁止复用旧行情、旧事件、旧股票或黄金样本数据。
3. 先读取31个申万一级行业，再动态确定领涨、领跌、转强、异常放量和背离板块。不得预设科技、航天、医药或任何行业。
4. 分开标记 `fact_fin_db`、`fact_search`、`calculated`、`inferred`、`forecast` 与 `missing`。
5. 新闻存在不等于新闻导致涨跌。归因必须检查事件时序、价格、成交、宽度、产业传导、基本面和替代解释。
6. 资金迁移只能标记为 `inferred`，不得声称账户穿透流向。
7. 缺失数据保留原UI模块并标注“未核验”；不得删模块或用0、旧值补位。
8. 公司关键风险字段不完整时关闭核心池和正式TOP 5。
9. 只允许 `scripts/render_golden_console.py` 生成正式HTML；不得让AI重写CSS、DOM、卡片体系或整页 `innerHTML`。
10. 必须同时交付统一入口及市场地图、未来预测、选股中心四个HTML。
11. 三个页面的全部事实型与预测型槽位都必须由本次Bundle覆盖；禁止保留黄金母版的板块、概率、事件、日期、涨跌颜色、图表位置或按钮目标。
12. 数字、颜色、图表和交互必须语义一致：上涨红、下跌绿；置信度数字等于进度条；股票池按钮必须进入文字对应层级；七日时间轴不得出现空白日期卡片。

## 首次运行检查

执行：

```bash
python3 scripts/preflight.py
```

要求Python 3.9+、`lxml`、Yixin密钥映射。Chrome用于运行时验收；缺失Chrome时不得声称完成浏览器验收。

## 标准执行

为本次日期创建全新运行目录；不要把 `runs/latest` 指向含旧数据的目录。

```bash
python3 scripts/run_workflow.py --stage init --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage collect --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage normalize --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage scope --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage catalysts --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage normalize --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage baseline --run runs/YYYY-MM-DD
python3 scripts/run_workflow.py --stage work-order --run runs/YYYY-MM-DD
```

以上步骤只产生保守基准草稿Bundle和 `analysis/analysis-work-order.json`，不得作为正式报告发布。

## AI证据分析

读取以下文件：

- `references/final-workflow.md`
- `references/data-contract.md`
- `references/source-policy.md`
- `references/dynamic-sector-attribution.md`
- `references/forecast-contract.md`
- `references/stock-selection-contract.md`
- `references/risk-gates.md`
- `references/analysis-overrides.md`
- `analysis/analysis-work-order.json`

逐个阅读本次动态板块对应的 `normalized/catalysts.json` 与原始Search响应。将增强分析只写入：

```text
analysis/analysis-overrides.json
```

该文件是Bundle的局部补丁。不得覆盖交易日、指数、市场宽度、31行业事实和证据账本。不得直接修改黄金HTML。

如果需要公司级选股：

1. 根据动态行业、真实催化和产业链位置创建 `analysis/stock-universe.json`。
2. 运行 `python3 scripts/run_workflow.py --stage collect-stocks --run runs/YYYY-MM-DD`。
3. 阅读公司Fin DB证据和公告风险证据。
4. 在 `analysis-overrides.json` 中形成候选、重点、核心三层池。
5. 关键风险未完整时不得发布正式TOP 5。

## 发布与验收

执行：

```bash
python3 scripts/run_workflow.py --stage publish --run runs/YYYY-MM-DD
```

`publish` 固定执行：

```text
合并基准Bundle与AI补丁
→ 拒绝缺少AI证据分析的基准草稿
→ Bundle契约和证据引用校验
→ 黄金母版哈希校验
→ 仅修改黄金DOM数据叶子并渲染四个HTML
→ CSS、完整DOM同构、31行业、预测页母版残留校验
→ 涨跌颜色、图表数值、事件日期、股票池按钮与草稿标识语义校验
→ Chrome运行时DOM校验
```

正式产物：

```text
reports/market-intelligence-console.html
reports/market-map.html
reports/market-forecast.html
reports/stock-selection-center.html
bundle.json
analysis/evidence.json
run-metadata.json
```

## 无AI增强的一键安全模式

需要快速生成保守版本时执行：

```bash
python3 scripts/run_workflow.py --stage full --run runs/YYYY-MM-DD
```

该模式仍获取最新Yixin数据并输出完整UI，但对无法从价格事实确认的催化、事件和公司结论显示“未核验”，不会伪造深度分析。
产物写入 `reports-draft/`，不会占用正式 `reports/` 目录，也不得对外称为正式市场研究控制台。

## 返回用户

报告最新完成交易日、风险指数、动态板块、行业覆盖率、三层股票池数量、正式TOP 5状态、关键数据缺口、验证状态，并给出四个HTML的绝对路径。明确内容为研究信息，不构成投资建议。
