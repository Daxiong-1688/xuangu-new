#!/usr/bin/env python3
import argparse
from datetime import date
from workflow_lib import SHENWAN31, read_json

def fail(errors):
    if errors:raise SystemExit("BUNDLE INVALID\n- "+"\n- ".join(errors))

def main():
    p=argparse.ArgumentParser();p.add_argument("--bundle",required=True);args=p.parse_args();b=read_json(args.bundle,{})
    errors=[];top={"metadata","market_map","forecast","stock_pools","risk_audit","evidence"}
    if set(b)!=top:errors.append("顶层结构必须严格等于 "+str(sorted(top)))
    m=b.get("market_map",{});f=b.get("forecast",{});s=b.get("stock_pools",{});r=b.get("risk_audit",{})
    metadata=b.get("metadata",{})
    resolved=metadata.get("resolved_trading_date")
    try:
        if not resolved or date.fromisoformat(resolved)>date.today():errors.append("交易日缺失或晚于当前日期")
    except ValueError:errors.append("交易日必须为YYYY-MM-DD")
    risk=m.get("risk_score")
    if not isinstance(risk,(int,float)) or not 0<=risk<=100:errors.append("风险指数必须在0—100")
    inds=m.get("industries",[]);names={x.get("name") for x in inds if isinstance(x,dict)}
    if len(inds)!=31 or names!=set(SHENWAN31):errors.append("行业全景必须保留31个申万一级行业")
    scope={x.get("sector") for x in m.get("dynamic_sector_scope",[]) if isinstance(x,dict)}
    attrs={x.get("sector") for x in m.get("sector_attribution",[]) if isinstance(x,dict)}
    if scope and not scope.issubset(attrs):errors.append("每个动态入选板块都必须完成涨跌归因")
    for x in m.get("sector_attribution",[]):
        for key in ("primary_reason","alternative_explanations","continuation_conditions","invalidating_signals","evidence_ids"):
            if not x.get(key):errors.append(f"{x.get('sector','未知板块')} 缺少 {key}")
    horizons=f.get("horizons",[])
    if {x.get("period") for x in horizons}!={"1—3日","1—2周","1—3月"}:errors.append("预测必须包含三个固定周期")
    if sum(float(x.get("weight",0)) for x in f.get("scenarios",[]))!=100:errors.append("三情景权重必须合计100")
    if s.get("formal_top5",{}).get("published") and not r.get("critical_complete"):errors.append("关键风险不完整时不得发布正式TOP 5")
    if s.get("formal_top5",{}).get("published") and len(s.get("core",[]))<5:errors.append("正式TOP 5发布时核心池不得少于5家公司")
    if not m.get("data_gaps"):errors.append("必须公开数据缺口")
    evidence_ids={x.get("id") for x in b.get("evidence",[]) if isinstance(x,dict)}
    for x in m.get("sector_attribution",[]):
        unknown=set(x.get("evidence_ids",[]))-evidence_ids
        if unknown:errors.append(f"{x.get('sector','未知板块')}引用不存在的证据：{sorted(unknown)}")
    allowed={"fact_fin_db","fact_search","calculated","inferred","forecast","missing"}
    for item in b.get("evidence",[]):
        if item.get("status") not in allowed:errors.append(f"证据{item.get('id')}状态非法：{item.get('status')}")
    fail(errors);print("BUNDLE VALID")

if __name__=="__main__":main()
