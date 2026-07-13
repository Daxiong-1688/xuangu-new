# AI分析补丁契约

## 目的

把AI判断限制为对保守基准Bundle的局部增强，不允许AI重新生成事实层、数据结构或HTML。

## 输出

只写 `analysis/analysis-overrides.json`。文件可以包含：

- `market_map.core_conclusion`
- `market_map.decision_conflict`
- `market_map.sector_attribution`
- `market_map.fund_migration`
- `market_map.lifecycle`
- `market_map.daily_validation`
- `market_map.events`
- `market_map.macro_factors`
- `market_map.signals`
- `forecast`
- `stock_pools`
- `risk_audit`

禁止覆盖：

- `metadata.resolved_trading_date`
- `metadata.data_source`
- `market_map.indices`
- `market_map.breadth`
- `market_map.industries`
- `evidence`

## 归因要求

每个动态板块必须包含主因、次因、替代解释、行情性质、资金推断、产业传导、基本面确认、宏观传导、置信度、持续条件、反证信号和本次运行的 `evidence_ids`。

当催化只有搜索摘要、缺少价格时序或公司兑现证据时，降低置信度并写明“事件相关性待验证”。不得为了让页面内容丰富而提高置信度。

## 事件要求

只有确认尚未发生、时间、时区和来源的事件才能进入 `market_map.events`。字段包括：`event`、`datetime`、`timezone`、`importance`、`verification_status`、`source_url`、`impact_channels` 和 `evidence_ids`。

## 股票池要求

候选、重点和核心层级必须逐级满足研究契约。个股至少保留名称、代码、行业、产业链位置、入池理由、财务报告期、营收和利润增长、现金流、技术结构、风险摘要及证据ID。关键风险不完整时核心池为空、`formal_top5.published=false`。
