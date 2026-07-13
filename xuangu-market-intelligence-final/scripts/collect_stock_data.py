#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path

from workflow_lib import read_json, write_json
from yixin_client import call, load_keys, save_raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    run = Path(args.run).resolve()
    universe = read_json(run / "analysis/stock-universe.json", {}).get("stocks", [])
    if not universe:
        write_json(run / "normalized/stocks.json", {"stocks": [], "missing_reason": "analysis/stock-universe.json为空；未执行公司级查询"})
        print("STOCK COLLECTION SKIPPED · empty universe")
        return
    trade_date = read_json(run / "run-metadata.json", {}).get("resolved_trading_date")
    keys = load_keys()
    raw_dir = run / "raw"
    plans = []
    for index, stock in enumerate(universe, 1):
        identity = f"{stock.get('name','')}（{stock.get('code','')}）"
        sector = stock.get("sector", "")
        fin_query = (
            f"查询A股公司{identity}截至{trade_date}可获得的最新财务报告期、主营业务及{sector}相关业务占比、"
            "营业收入及同比、归母净利润及同比、经营现金流、应收账款、订单或合同，并查询5/20/60日涨跌幅、"
            "5/20/60日均线位置和52周价格位置。逐字段返回并标明报告期。"
        )
        risk_query = (
            f"核验A股公司{identity}截至{trade_date}最近6个月的减持、解禁、监管处罚、立案调查、诉讼、"
            "退市风险、业绩预告暴雷和重大公告；优先交易所、监管和公司公告，逐项给出日期和链接。"
        )
        plans.extend([
            (f"ST{index:03d}", "fin_db", fin_query, {}),
            (f"SR{index:03d}", "search", risk_query, {"source": "announcement", "time_range": "past 6 months", "count": 25}),
        ])

    def execute(plan):
        evidence_id, api, query, options = plan
        response = call(api, query, keys[api], **options)
        return save_raw(raw_dir, evidence_id, api, query, response)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        manifest = list(pool.map(execute, plans))
    write_json(raw_dir / "stock-manifest.json", manifest)
    write_json(run / "normalized/stocks.json", {
        "stocks": [{**item, "fin_evidence_id": f"ST{index:03d}", "risk_evidence_id": f"SR{index:03d}", "status": "requires_ai_normalization"} for index, item in enumerate(universe, 1)],
        "missing_reason": "公司级原始证据已采集；须依照风险门槛标准化后才能升级股票池",
    })
    print(json.dumps({"stocks": len(universe), "queries": len(plans)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
