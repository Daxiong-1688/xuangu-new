#!/usr/bin/env python3
import argparse
from pathlib import Path
from workflow_lib import read_json

def main():
    p=argparse.ArgumentParser();p.add_argument("--run",required=True);p.add_argument("--allow-draft",action="store_true");a=p.parse_args();root=Path(a.run).resolve()
    overrides=read_json(root/"analysis/analysis-overrides.json",{})
    bundle=read_json(root/"bundle.json",{})
    errors=[]
    if not overrides:errors.append("缺少AI证据分析补丁 analysis/analysis-overrides.json")
    if bundle.get("metadata",{}).get("analysis_mode")!="evidence_constrained_ai":errors.append("analysis_mode仍是基准草稿")
    attrs=bundle.get("market_map",{}).get("sector_attribution",[])
    if not attrs:errors.append("没有完成动态板块涨跌归因")
    if any(not x.get("evidence_ids") or not x.get("alternative_explanations") for x in attrs):errors.append("板块归因缺少证据或替代解释")
    if errors and not a.allow_draft:raise SystemExit("FORMAL PUBLISH BLOCKED\n- "+"\n- ".join(errors))
    print("ANALYSIS READY" if not errors else "DRAFT MODE · "+"；".join(errors))

if __name__=="__main__":main()
