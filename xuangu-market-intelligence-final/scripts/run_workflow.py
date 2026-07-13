#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parent

def run(name,*args):
    subprocess.run([sys.executable,str(SCRIPTS/name),*map(str,args)],check=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage",choices=["init","collect","normalize","scope","catalysts","collect-stocks","baseline","work-order","assemble","validate","render","runtime-validate","publish","full"],required=True)
    p.add_argument("--run",required=True)
    p.add_argument("--bundle")
    p.add_argument("--allow-draft",action="store_true")
    args=p.parse_args();root=Path(args.run).resolve()
    if args.stage=="init":run("init_run.py","--output",root)
    elif args.stage=="collect":run("collect_yixin_data.py","--run",root,"--mode","core")
    elif args.stage=="normalize":run("normalize_yixin.py","--run",root)
    elif args.stage=="scope":run("select_dynamic_sectors.py","--industries",root/"normalized/industries.json","--output",root/"analysis/sector-scope.json")
    elif args.stage=="catalysts":run("collect_yixin_data.py","--run",root,"--mode","catalysts")
    elif args.stage=="collect-stocks":run("collect_stock_data.py","--run",root)
    elif args.stage=="baseline":run("build_baseline_bundle.py","--run",root)
    elif args.stage=="work-order":run("create_analysis_work_order.py","--run",root)
    elif args.stage=="assemble":run("assemble_bundle.py","--run",root)
    elif args.stage=="validate":run("validate_bundle.py","--bundle",args.bundle or root/"bundle.json")
    elif args.stage=="render":
        run("validate_analysis_ready.py","--run",root,*(["--allow-draft"] if args.allow_draft else []))
        output=root/("reports-draft" if args.allow_draft else "reports")
        run("render_golden_console.py","--bundle",args.bundle or root/"bundle.json","--output",output)
        for name in ("market-intelligence-console.html","market-map.html","market-forecast.html","stock-selection-center.html"):
            run("validate_rendered_console.py","--html",output/name,"--bundle",args.bundle or root/"bundle.json")
    elif args.stage=="runtime-validate":
        output=root/("reports-draft" if args.allow_draft else "reports")
        run("validate_runtime_console.py","--reports",output,"--bundle",args.bundle or root/"bundle.json")
    elif args.stage=="publish":
        run("assemble_bundle.py","--run",root)
        run("validate_analysis_ready.py","--run",root)
        run("validate_bundle.py","--bundle",root/"bundle.json")
        run("check_golden_integrity.py")
        run("render_golden_console.py","--bundle",root/"bundle.json","--output",root/"reports")
        for name in ("market-intelligence-console.html","market-map.html","market-forecast.html","stock-selection-center.html"):
            run("validate_rendered_console.py","--html",root/"reports"/name,"--bundle",root/"bundle.json")
        run("validate_runtime_console.py","--reports",root/"reports","--bundle",root/"bundle.json")
    elif args.stage=="full":
        run("init_run.py","--output",root)
        run("collect_yixin_data.py","--run",root,"--mode","core")
        run("normalize_yixin.py","--run",root)
        run("select_dynamic_sectors.py","--industries",root/"normalized/industries.json","--output",root/"analysis/sector-scope.json")
        run("collect_yixin_data.py","--run",root,"--mode","catalysts")
        run("normalize_yixin.py","--run",root)
        run("build_baseline_bundle.py","--run",root)
        run("create_analysis_work_order.py","--run",root)
        run("assemble_bundle.py","--run",root)
        run("validate_analysis_ready.py","--run",root,"--allow-draft")
        run("validate_bundle.py","--bundle",root/"bundle.json")
        run("check_golden_integrity.py")
        run("render_golden_console.py","--bundle",root/"bundle.json","--output",root/"reports-draft")
        for name in ("market-intelligence-console.html","market-map.html","market-forecast.html","stock-selection-center.html"):
            run("validate_rendered_console.py","--html",root/"reports-draft"/name,"--bundle",root/"bundle.json")
        run("validate_runtime_console.py","--reports",root/"reports-draft","--bundle",root/"bundle.json")

if __name__=="__main__":main()
