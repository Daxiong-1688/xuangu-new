#!/usr/bin/env python3
import hashlib
import re
from pathlib import Path

EXPECTED="f778e87122000ce6d9bb272f91ba1e0d0400d534d628ec7f7e0f3b85aeba8538"
REQUIRED={"market","prediction","stocks","overview","decision","matrix","causes","breadth","industries","capital","lifecycle","daily","events","evidence","forecastMount","stockRisk","stockFunnel","stockPools","stockTop","drawer"}

def main():
    root=Path(__file__).resolve().parents[1]
    path=root/"assets/golden/market-intelligence-console.html"
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();text=raw.decode("utf-8")
    ids=set(re.findall(r'id="([^"]+)"',text));missing=sorted(REQUIRED-ids)
    if digest!=EXPECTED:raise SystemExit(f"GOLDEN HASH CHANGED: {digest}")
    if missing:raise SystemExit("GOLDEN MODULES MISSING: "+", ".join(missing))
    print("GOLDEN UI INTEGRITY OK")

if __name__=="__main__":main()

