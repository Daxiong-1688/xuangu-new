#!/usr/bin/env python3
import argparse
import math
import statistics
from workflow_lib import SHENWAN31, number, read_json, write_json

def zscores(values):
    clean=[v for v in values if v is not None]
    if len(clean)<2:return [0 if v is not None else None for v in values]
    mean=statistics.fmean(clean);sd=statistics.pstdev(clean)
    return [None if v is None else 0 if sd==0 else (v-mean)/sd for v in values]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--industries", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--leaders", type=int, default=5)
    p.add_argument("--laggards", type=int, default=5)
    args=p.parse_args()
    rows=read_json(args.industries, [])
    by_name={x.get("name"):x for x in rows if isinstance(x,dict)}
    canonical=[by_name.get(name,{"name":name}) for name in SHENWAN31]
    d1=[number(x.get("d1")) for x in canonical]
    d5=[number(x.get("d5")) for x in canonical]
    d20=[number(x.get("d20")) for x in canonical]
    rv=[number(x.get("relative_volume")) for x in canonical]
    z1=zscores(d1);zv=zscores(rv)
    valid=sorted([(v,i) for i,v in enumerate(d1) if v is not None], reverse=True)
    leader_n=min(args.leaders,max(1,len(valid)//3)) if valid else 0
    laggard_n=min(args.laggards,max(1,len(valid)//3)) if valid else 0
    leader_idx={i for _,i in valid[:leader_n]};laggard_idx={i for _,i in valid[-laggard_n:]}
    selected=[]
    for i,x in enumerate(canonical):
        reasons=[]
        if i in leader_idx:reasons.append("leader")
        if i in laggard_idx:reasons.append("laggard")
        if d1[i] is not None and d5[i] is not None and d20[i] is not None and d1[i]>0 and d5[i]>d20[i]/4:reasons.append("strengthening")
        if zv[i] is not None and zv[i]>=1.5:reasons.append("abnormal_volume")
        breadth=number(x.get("breadth_ratio"))
        if d1[i] is not None and breadth is not None and ((d1[i]>0 and breadth<0.4) or (d1[i]<0 and breadth>0.6)):reasons.append("divergence")
        if reasons:
            selected.append({"sector":x["name"],"selection_reasons":reasons,"d1":d1[i],"d5":d5[i],"d20":d20[i],"relative_volume":rv[i],"zscore_1d":z1[i],"zscore_volume":zv[i],"evidence_ids":x.get("evidence_ids",[])})
    write_json(args.output,{"method":"cross_sectional_dynamic_selection","coverage":len(valid),"selected":selected,"missing_count":31-len(valid),"hardcoded_sectors":False})
    print(f"selected={len(selected)} coverage={len(valid)}/31")

if __name__=="__main__":main()
