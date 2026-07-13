#!/usr/bin/env python3
import argparse
from pathlib import Path
from workflow_lib import read_json, write_json

def main():
    p=argparse.ArgumentParser();p.add_argument("--run",required=True);args=p.parse_args();root=Path(args.run)
    scope=read_json(root/"analysis/sector-scope.json",{})
    order={
      "instruction":"Analyze only sectors selected from this run. Write analysis/analysis-overrides.json as a partial Bundle patch. Apply six-lens attribution, cite evidence_ids, and never override protected market facts.",
      "output_file":"analysis/analysis-overrides.json",
      "protected_paths":["metadata.resolved_trading_date","metadata.data_source","market_map.indices","market_map.breadth","market_map.industries","evidence"],
      "sector_scope":scope.get("selected",[]),
      "required_lenses":["price_and_chips","fund_behavior","catalyst","industry_transmission","fundamental_confirmation","macro_transmission"],
      "required_outputs":["primary_reason","secondary_reasons","alternative_explanations","nature","confidence","continuation_conditions","invalidating_signals","evidence_ids"],
      "rules":["新闻存在不等于新闻导致涨跌","资金流向只能标记inferred","未来事件必须核验发生时间和时区","关键个股风险不完整时关闭核心池和正式TOP5","不得固定科技、航天、医药或任何历史行业"],
      "market_inputs":read_json(root/"normalized/market.json",{}),
      "industry_inputs":read_json(root/"normalized/industries.json",[]),
      "event_inputs":read_json(root/"normalized/events.json",{}),
      "catalyst_inputs":read_json(root/"normalized/catalysts.json",{}),
      "stock_inputs":read_json(root/"normalized/stocks.json",{}),
      "evidence_ledger":read_json(root/"analysis/evidence.json",[]),
      "baseline_bundle":read_json(root/"analysis/baseline-bundle.json",{})
    }
    write_json(root/"analysis/analysis-work-order.json",order)
    print(root/"analysis/analysis-work-order.json")

if __name__=="__main__":main()
