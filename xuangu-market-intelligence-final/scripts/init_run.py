#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path
from workflow_lib import write_json

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);args=p.parse_args();root=Path(args.output).resolve()
    for name in ("raw","normalized","features","analysis","reports"):(root/name).mkdir(parents=True,exist_ok=True)
    write_json(root/"run-metadata.json",{"schema_version":"2.0.0","generated_at":datetime.now(timezone.utc).isoformat(),"stage":"initialized","data_source":"Yixin Search + Fin DB","no_stale_data":True})
    print(root)

if __name__=="__main__":main()

