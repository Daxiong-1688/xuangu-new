# 数据契约

## 分层

- `raw`：原始API响应，不改写。
- `normalized`：类型化事实。
- `features`：确定性计算。
- `analysis`：推断和预测。
- `reports`：只负责展示。

## 字段信封

```json
{
  "value": null,
  "unit": null,
  "as_of": null,
  "status": "missing",
  "confidence": 0,
  "evidence_ids": [],
  "missing_reason": null
}
```

状态枚举：`fact_fin_db`、`fact_search`、`calculated`、`inferred`、`forecast`、`missing`。

## 关键约束

- 日期使用 `YYYY-MM-DD`，时间使用含时区ISO 8601。
- 收益率使用百分数值而非小数。
- A股成交额统一为亿元。
- 行业固定为31个申万一级行业，但分析对象由当天数据动态选择。
- 缺失为 `null`，不能使用0替代。
- 行业收益采用统一行业指数口径，不混用成分股平均。
- 页面与JSON不得残留上一次运行的数据。

