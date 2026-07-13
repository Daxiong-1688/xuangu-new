#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from workflow_lib import SHENWAN31, read_json, write_json
from yixin_client import call, load_keys, now_iso, save_raw

INDICES = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "北证50"]


def result_text(value) -> str:
    return json.dumps(value.get("result", value), ensure_ascii=False) if isinstance(value, dict) else str(value)


def resolve_trade_date(response: dict) -> str | None:
    values = []
    for year, month, day in re.findall(r"\b(20\d{2})[-/]?(\d{2})[-/]?(\d{2})\b", result_text(response)):
        try:
            candidate = date(int(year), int(month), int(day))
            if candidate <= datetime.now(ZoneInfo("Asia/Shanghai")).date():
                values.append(candidate)
        except ValueError:
            pass
    return max(values).isoformat() if values else None


def execute_plans(plans, keys, raw_dir: Path, workers: int):
    def execute(plan):
        evidence_id, api, query, options = plan
        response = call(api, query, keys[api], **options)
        return save_raw(raw_dir, evidence_id, api, query, response)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(execute, plans))


def collect_core(run: Path, workers: int):
    raw_dir = run / "raw"
    keys = load_keys()
    query = (
        "查询最新已完成交易日A股上涨家数、下跌家数、平盘家数、涨停数量、跌停数量、"
        "总成交额，以及前一交易日总成交额。明确返回交易日期YYYY-MM-DD，成交额单位亿元。"
    )
    first = call("fin_db", query, keys["fin_db"])
    manifest = [save_raw(raw_dir, "M000", "fin_db", query, first)]
    trade_date = resolve_trade_date(first)
    if not trade_date:
        raise SystemExit("BLOCKED：无法从本次Yixin响应确定最新完成交易日；禁止复用旧数据")

    plans = []
    for index, name in enumerate(INDICES, 1):
        query = f"查询{name}在{trade_date}的收盘点位和当日涨跌幅。仅返回指数名称、交易日期、收盘点位和涨跌幅。"
        plans.append((f"IX{index:02d}", "fin_db", query, {}))
    for index, name in enumerate(SHENWAN31, 1):
        query = (
            f"查询申万一级行业指数{name}截至{trade_date}的当日涨跌幅、近5个交易日累计涨跌幅、"
            f"近20个交易日累计涨跌幅和当日成交额。仅返回{name}这一行业指数，单位为%和亿元。"
        )
        plans.append((f"SI{index:02d}", "fin_db", query, {}))
    # Batch queries provide a second, independent fallback because Fin DB coverage
    # can differ between single-industry and multi-industry natural-language calls.
    for group_index in range(0, len(SHENWAN31), 5):
        names = SHENWAN31[group_index:group_index + 5]
        query = (
            f"查询以下申万一级行业指数截至{trade_date}的当日涨跌幅、近5个交易日累计涨跌幅、"
            f"近20个交易日累计涨跌幅和当日成交额：{'、'.join(names)}。逐行业逐字段返回，单位为%和亿元。"
        )
        plans.append((f"IG{group_index // 5 + 1:02d}", "fin_db", query, {}))

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    end = now.date() + timedelta(days=7)
    plans.extend([
        ("G001", "search",
         f"截至北京时间{now.isoformat()}，查询最新可用的道琼斯、标普500、纳斯达克、费城半导体、"
         "美国10年期国债收益率、美元指数、黄金、原油、离岸人民币、恒生指数和恒生科技表现；"
         "明确各自数据日期和涨跌幅。",
         {"time_range": "past 1 week", "count": 30}),
        ("C001", "search",
         f"{trade_date} A股收盘市场宽度、成交变化、申万一级行业领涨领跌和权威盘后复盘；"
         "保留事件时间、来源与可能的替代解释。",
         {"time_range": "past 1 week", "count": 30}),
        ("E001", "search",
         f"从{now.date().isoformat()}到{end.isoformat()}尚未发生、可能影响A股和美股的全球经济数据、"
         "央行会议、重要财报、政策、产业会议和地缘事件；优先官方来源并给出北京时间。",
         {"time_range": f"from {now.date().isoformat()} to {end.isoformat()}", "count": 40}),
    ])
    manifest.extend(execute_plans(plans, keys, raw_dir, workers))
    metadata = read_json(run / "run-metadata.json", {})
    metadata.update({
        "resolved_trading_date": trade_date,
        "retrieved_at": now_iso(),
        "source": "Yixin Search + Fin DB",
        "fresh_run": True,
        "core_manifest_count": len(manifest),
    })
    write_json(run / "run-metadata.json", metadata)
    write_json(raw_dir / "manifest.json", manifest)
    print(json.dumps({"trade_date": trade_date, "queries": len(manifest)}, ensure_ascii=False))


def collect_catalysts(run: Path, workers: int):
    scope = read_json(run / "analysis/sector-scope.json", {}).get("selected", [])
    if not scope:
        raise SystemExit("BLOCKED：动态板块范围为空；先运行normalize和scope")
    trade_date = read_json(run / "run-metadata.json", {}).get("resolved_trading_date")
    keys = load_keys()
    raw_dir = run / "raw"
    plans = []
    for index, item in enumerate(scope, 1):
        sector = item.get("sector")
        if not sector:
            continue
        query = (
            f"分析{trade_date} A股申万一级{sector}行业涨跌的真实原因。查找当日及此前7天的政策、公告、"
            "产业价格、订单、业绩与权威复盘；区分已验证事实、市场解释和替代解释，不把新闻存在直接当作涨跌原因。"
        )
        plans.append((f"CA{index:02d}", "search", query, {"time_range": "past 1 week", "count": 25}))
    manifest = execute_plans(plans, keys, raw_dir, workers)
    write_json(raw_dir / "catalyst-manifest.json", manifest)
    print(json.dumps({"dynamic_sectors": len(plans), "queries": len(manifest)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--mode", choices=["core", "catalysts"], default="core")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run = Path(args.run).resolve()
    if args.mode == "core":
        collect_core(run, args.workers)
    else:
        collect_catalysts(run, args.workers)


if __name__ == "__main__":
    main()
