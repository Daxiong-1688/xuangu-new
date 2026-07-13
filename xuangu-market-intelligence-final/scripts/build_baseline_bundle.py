#!/usr/bin/env python3
"""Build a conservative, fully traceable bundle before AI enrichment.

This script never invents catalysts, company quality, fund flows, or future events.
It converts verified price/breadth facts into deterministic classifications and
leaves evidence-sensitive narrative fields explicitly unverified.
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from workflow_lib import read_json, write_json


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def num(value):
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def integer(value):
    return int(round(value)) if num(value) is not None else None


def risk_model(breadth: dict, industries: list[dict]):
    up, down, flat = (num(breadth.get(key)) for key in ("up", "down", "flat"))
    total = sum(x or 0 for x in (up, down, flat))
    up_ratio = up / total if total else None
    if up_ratio is None:
        breadth_risk = 20
    else:
        breadth_risk = clamp((0.55 - up_ratio) / 0.50 * 35, 0, 35)
    limit_down = num(breadth.get("limit_down"))
    tail_risk = clamp((limit_down or 0) / 120 * 25, 0, 25) if limit_down is not None else 12
    turnover_change = num(breadth.get("turnover_change_pct"))
    liquidity_risk = 7
    if turnover_change is not None:
        if up_ratio is not None and up_ratio < 0.35 and turnover_change < 0:
            liquidity_risk = clamp(7 + abs(turnover_change) / 20 * 8, 7, 15)
        elif up_ratio is not None and up_ratio < 0.35 and turnover_change >= 0:
            liquidity_risk = clamp(9 + turnover_change / 15 * 6, 9, 15)
        else:
            liquidity_risk = clamp(5 - turnover_change / 20 * 3, 2, 9)
    usable = [item for item in industries if num(item.get("d1")) is not None]
    industry_positive = sum(num(item.get("d1")) >= 0 for item in usable)
    industry_ratio = industry_positive / len(usable) if usable else None
    industry_risk = 8 if industry_ratio is None else clamp((0.55 - industry_ratio) / 0.55 * 15, 0, 15)
    missing_penalty = clamp((31 - len(usable)) / 31 * 10, 0, 10)
    components = {
        "breadth": round(breadth_risk),
        "tail_risk": round(tail_risk),
        "liquidity": round(liquidity_risk),
        "industry_structure": round(industry_risk),
        "data_uncertainty": round(missing_penalty),
    }
    return round(sum(components.values())), components, up_ratio, industry_ratio


def regime_for(score: int, up_ratio):
    if score >= 80:
        return "high_risk_deleveraging", "高风险去杠杆"
    if score >= 65:
        return "risk_off", "风险收缩"
    if score >= 45:
        return "volatile_rotation", "高波动轮动"
    if up_ratio is not None and up_ratio >= 0.62:
        return "risk_on_expansion", "风险偏好扩张"
    return "balanced_structure", "结构性平衡"


def trend_nature(item: dict):
    d1, d5, d20 = (num(item.get(key)) for key in ("d1", "d5", "d20"))
    if d1 is None:
        return "数据不足", "缺少可靠行业指数涨跌数据"
    if d1 >= 0 and d5 is not None and d5 < 0:
        return "超跌反弹", "短线由弱转强，但中期趋势尚未确认"
    if d1 >= 0 and (d5 is None or d5 >= 0):
        return "风格轮动", "当日及短周期保持相对强势，是否为产业趋势仍需催化与基本面验证"
    if d20 is not None and d20 > 0 and d1 < 0:
        return "获利兑现", "中期仍有累计涨幅，但短线转弱，符合筹码兑现或拥挤度下降特征"
    if d5 is not None and d20 is not None and d1 < 0 and d5 < 0 and d20 < 0:
        return "风险扩散", "1日、5日和20日同步偏弱，弱势并非单日噪声"
    return "宏观传导", "行业随市场风险偏好变化，暂缺独立产业证据"


def attribution(scope: list[dict], risk_score: int):
    output = []
    for item in scope:
        sector = item.get("sector")
        nature, reason = trend_nature(item)
        d1, d5, d20 = (num(item.get(key)) for key in ("d1", "d5", "d20"))
        direction = "相对承接" if d1 is not None and d1 >= 0 else "风险暴露下降"
        confidence = 0.62 if all(x is not None for x in (d1, d5, d20)) else 0.48
        output.append({
            "sector": sector,
            "facts": {"d1": d1, "d5": d5, "d20": d20, "turnover": num(item.get("turnover"))},
            "primary_reason": reason,
            "secondary_reasons": [
                f"市场风险指数为{risk_score}/100，系统性风险偏好会放大行业自身波动",
                "动态催化已检索，因果关系需结合事件时序、成交和行业扩散由AI进一步核验",
            ],
            "alternative_explanations": [
                "全市场共同涨跌可能放大行业表现",
                "行业指数、龙头和多数成分股可能存在强弱背离，成分股宽度尚未核验",
            ],
            "nature": nature,
            "fund_behavior": {
                "status": "inferred",
                "summary": f"根据相对收益推断资金呈现{direction}；这不是账户穿透流向",
            },
            "industry_transmission": "上游价格、中游订单和下游需求尚待公司级证据核验",
            "fundamental_confirmation": "订单、利润、现金流、库存和应收尚未完成公司级验证",
            "macro_transmission": "利率、汇率、商品、政策与外部风险通过市场风险预算传导",
            "confidence": confidence,
            "continuation_conditions": ["行业相对收益延续", "成交和行业宽度与价格方向共振"],
            "invalidating_signals": ["行业次日快速反向且成交不支持", "公司基本面证据与价格叙事相冲突"],
            "evidence_ids": list(item.get("evidence_ids", [])),
        })
    return output


def risk_language(score: int):
    if score >= 80:
        return "高风险，只观察，不猜底"
    if score >= 65:
        return "风险偏高，控制仓位并等待宽度修复"
    if score >= 45:
        return "高波动结构行情，优先相对强势与基本面确认"
    return "风险可控，但仍需行业和公司双重确认"


def build(run: Path):
    metadata = read_json(run / "run-metadata.json", {})
    market = read_json(run / "normalized/market.json", {})
    industries = read_json(run / "normalized/industries.json", [])
    events = read_json(run / "normalized/events.json", {}).get("events", [])
    scope = read_json(run / "analysis/sector-scope.json", {}).get("selected", [])
    evidence = read_json(run / "analysis/evidence.json", [])
    breadth = market.get("breadth", {})
    trade_date = metadata.get("resolved_trading_date") or market.get("trade_date")
    risk_score, risk_components, up_ratio, industry_ratio = risk_model(breadth, industries)
    regime, regime_label = regime_for(risk_score, up_ratio)
    usable = sum(num(item.get("d1")) is not None for item in industries)
    valid_scope = [x for x in scope if num(x.get("d1")) is not None]
    leader = max(valid_scope, key=lambda x: x["d1"], default={}).get("sector", "未核验")
    laggard = min(valid_scope, key=lambda x: x["d1"], default={}).get("sector", "未核验")
    up_text = integer(breadth.get("up"))
    down_text = integer(breadth.get("down"))
    core = (
        f"市场处于{regime_label}阶段。上涨{up_text if up_text is not None else '未核验'}家、"
        f"下跌{down_text if down_text is not None else '未核验'}家；动态相对强势方向为{leader}，"
        f"相对弱势方向包括{laggard}。当前先验证市场宽度与尾部风险，再讨论趋势反转。"
    )
    data_gaps = []
    if usable < 31:
        data_gaps.append(f"31个申万一级行业中仅{usable}个取得可靠行业指数数据，其余保留未核验")
    missing_indices = [x["name"] for x in market.get("indices", []) if x.get("status") == "missing"]
    if missing_indices:
        data_gaps.append("指数精确点位或涨跌幅未完整返回：" + "、".join(missing_indices))
    if not events:
        data_gaps.append("未来7天事件候选已检索，但尚未完成官方时间、时区和发生状态核验")
    data_gaps.extend([
        "行业相对成交量、成分股宽度、ETF申赎和融资融券尚未完整取得",
        "公司业务占比、财务、技术结构、减持、解禁、监管和诉讼尚未完整核验",
    ])
    d1_values = [num(x.get("d1")) for x in industries if num(x.get("d1")) is not None]
    positive_industries = sum(x >= 0 for x in d1_values)
    five_dimensions = [
        {"name": "趋势", "score": round(clamp(100 - risk_components["industry_structure"] * 4)), "summary": f"可用行业中{positive_industries}/{len(d1_values) or 0}上涨"},
        {"name": "宽度", "score": round(clamp((up_ratio or 0) * 100)), "summary": f"上涨{up_text if up_text is not None else '未核验'}、下跌{down_text if down_text is not None else '未核验'}"},
        {"name": "流动性", "score": round(clamp(100 - risk_components["liquidity"] * 5)), "summary": f"成交变化{breadth.get('turnover_change_pct') if breadth.get('turnover_change_pct') is not None else '未核验'}%"},
        {"name": "结构", "score": round(clamp((industry_ratio or 0) * 100)), "summary": "基于行业横截面强弱"},
        {"name": "风险", "score": risk_score, "summary": risk_language(risk_score)},
    ]
    dynamic_attrs = attribution(scope, risk_score)
    lifecycle = [{
        "theme": x.get("sector"),
        "stage": trend_nature(x)[0],
        "condition": "价格、成交、行业宽度和催化得到下一次验证",
    } for x in scope[:6]]
    next_day = (datetime.fromisoformat(trade_date).date() + timedelta(days=1)).isoformat() if trade_date else "下一交易日"
    daily_validation = [
        "上涨与下跌家数是否显著修复",
        "跌停数量是否收缩，尾部风险是否停止扩散",
        "领涨行业能否保持相对收益并向成分股扩散",
        "领跌行业是否缩量止跌或继续放量破位",
        "反弹时成交是否恢复，还是继续缩量承接不足",
    ]
    if risk_score >= 75:
        base_case = "未来1—3日仍以高波动和风险释放后的修复尝试为主；宽度与跌停未改善前，反弹不自动视为反转。"
        short_direction = "震荡偏弱，可能出现技术修复"
        style = "低波动和相对强势优先，高弹性方向先去拥挤"
    elif risk_score >= 50:
        base_case = "未来1—3日大概率维持结构轮动；指数方向弱于行业和公司分化的重要性。"
        short_direction = "震荡轮动"
        style = "相对强势行业与盈利确认优先"
    else:
        base_case = "未来1—3日风险偏好具备延续条件，但需要成交和行业扩散继续确认。"
        short_direction = "震荡偏强"
        style = "顺势但避免纯概念和高位拥挤"
    ranking = [{
        "sector": item.get("sector"),
        "view": "relative_bullish" if (num(item.get("d1")) or -999) >= 0 else "risk_watch",
        "confidence": 0.62 if num(item.get("d20")) is not None else 0.48,
        "action": "等待价格、宽度和催化共振",
        "strengthening_signal": "相对收益与成交同步改善",
        "invalidating_signal": "次日快速反向或基本面证据冲突",
    } for item in scope]
    bundle = {
        "metadata": {
            "schema_version": "3.0.0",
            "resolved_trading_date": trade_date,
            "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "data_source": "Yixin Search + Fin DB",
            "validation_status": "baseline_with_gaps",
            "analysis_mode": "deterministic_baseline",
        },
        "market_map": {
            "core_conclusion": core,
            "regime": regime,
            "regime_label": regime_label,
            "risk_score": risk_score,
            "risk_components": risk_components,
            "five_dimensions": five_dimensions,
            "decision_conflict": "市场价格、成交、宽度与产业催化可能相互冲突；当前基准版本只确认价格事实，催化因果等待证据约束分析。",
            "indices": market.get("indices", []),
            "breadth": breadth,
            "industries": industries,
            "dynamic_sector_scope": scope,
            "decision_matrix": [{
                "sector": x.get("sector"), "signal": trend_nature(x)[0],
                "selection_reasons": x.get("selection_reasons", []),
                "action": "等待下一验证信号",
            } for x in scope],
            "sector_attribution": dynamic_attrs,
            "fund_migration": {
                "status": "inferred",
                "path": "由领跌、高波动方向向相对强势、低波动方向迁移的可能性上升",
                "meaning": "这是基于价格、宽度和相对强弱的资金行为推断，不是账户级真实流向",
                "limits": "缺少ETF申赎、融资融券和账户穿透数据",
            },
            "lifecycle": lifecycle,
            "daily_validation": daily_validation,
            "events": events,
            "macro_factors": [
                {"name": "风险偏好", "summary": risk_language(risk_score)},
                {"name": "市场宽度", "summary": f"上涨占比{round((up_ratio or 0)*100, 1)}%" if up_ratio is not None else "未核验"},
                {"name": "流动性", "summary": f"成交额环比{round(breadth.get('turnover_change_pct'), 2)}%" if num(breadth.get("turnover_change_pct")) is not None else "未核验"},
                {"name": "未来事件", "summary": "事件候选须逐项核验后才能加入确定时间轴"},
            ],
            "signals": [
                {"name": "尾部风险", "level": "red" if risk_score >= 75 else "amber", "summary": f"跌停{integer(breadth.get('limit_down')) if num(breadth.get('limit_down')) is not None else '未核验'}家"},
                {"name": "市场宽度", "level": "red" if (up_ratio or 0) < 0.30 else "amber", "summary": f"上涨占比{round((up_ratio or 0)*100, 1)}%" if up_ratio is not None else "未核验"},
                {"name": "行业扩散", "level": "red" if (industry_ratio or 0) < 0.30 else "amber", "summary": f"可用行业上涨比例{round((industry_ratio or 0)*100, 1)}%" if industry_ratio is not None else "未核验"},
                {"name": "数据完整性", "level": "amber" if usable < 31 else "green", "summary": f"行业数据{usable}/31"},
            ],
            "comparison": [],
            "data_gaps": data_gaps,
        },
        "forecast": {
            "base_case": base_case,
            "confidence": 0.58 if usable < 20 else 0.68,
            "horizons": [
                {"period": "1—3日", "direction": short_direction, "style": style, "drivers": ["市场宽度", "尾部风险", "成交变化"], "conditions": ["当日数据结构延续"], "strengthening_signals": daily_validation[:3], "invalidating_signals": ["宽度和成交出现与基准路径相反的共振"], "next_validation": next_day},
                {"period": "1—2周", "direction": "由宏观数据、政策和盈利预期共同决定", "style": "防御与质量成长之间动态切换", "drivers": ["未来事件", "政策", "盈利预期"], "conditions": ["事件时点完成官方核验"], "strengthening_signals": ["指数、行业和公司形成三级共振"], "invalidating_signals": ["反弹缩量且领跌方向继续破位"], "next_validation": "未来7天事件落地后"},
                {"period": "1—3月", "direction": "维持条件性结构判断，不预测确定点位", "style": "盈利兑现优先于纯题材", "drivers": ["财报", "订单", "现金流", "宏观流动性"], "conditions": ["基本面没有持续下修"], "strengthening_signals": ["基本面与价格趋势共振"], "invalidating_signals": ["盈利预期与市场宽度同步恶化"], "next_validation": "下一财报验证窗口"},
            ],
            "scenarios": [
                {"name": "乐观", "weight": 20, "path": "尾部风险快速收缩，成交回升并出现行业扩散"},
                {"name": "基准", "weight": 50, "path": base_case},
                {"name": "谨慎", "weight": 30, "path": "宽度继续恶化，领跌方向扩散且流动性承接不足"},
            ],
            "sector_ranking": ranking,
            "fund_path": "先观察风险暴露是否由领跌方向向相对强势方向迁移；宽度修复后再判断是否回流高弹性板块",
            "market_rhythm": "先看尾部风险，再看指数，最后看行业与公司扩散",
            "invalidation_signals": ["市场宽度与当前基准方向显著相反", "成交与价格出现反向共振", "动态领涨板块次日快速补跌", "经核验的重大政策或地缘事件改变风险预算"],
        },
        "stock_pools": {
            "environment": f"风险指数{risk_score}/100；公司数据与关键风险不完整，只生成研究观察状态",
            "sector_mapping": [{"sector": x.get("sector"), "role": trend_nature(x)[0]} for x in scope],
            "score_model": {"market": 20, "sector": 20, "industry_chain": 15, "company_quality": 20, "technical": 15, "risk": 10},
            "candidate": [], "watch": [], "core": [], "company_comparison": [],
            "formal_top5": {"published": False, "reason": "公司基本面、技术结构与减持、解禁、监管、诉讼等关键风险尚未完整核验"},
        },
        "risk_audit": {
            "critical_complete": False,
            "items": [{"risk": "市场风险指数", "level": "high" if risk_score >= 75 else "medium", "evidence_ids": ["M000"]}],
            "missing_fields": ["减持", "解禁", "监管", "诉讼", "ETF申赎", "融资融券", "估值", "业务占比", "同比增长"],
        },
        "evidence": evidence,
    }
    write_json(run / "analysis/baseline-bundle.json", bundle)
    return bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    bundle = build(Path(args.run).resolve())
    print(f"BASELINE BUNDLE READY · risk={bundle['market_map']['risk_score']} · sectors={len(bundle['market_map']['dynamic_sector_scope'])}")


if __name__ == "__main__":
    main()
