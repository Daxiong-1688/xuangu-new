#!/usr/bin/env python3
import importlib.util
import json
import shutil
import sys
from pathlib import Path


def main():
    cache=Path("~/.cache/codex-runtimes").expanduser()
    playwright=any((p/"node/node_modules/playwright").exists() and (p/"node/bin/node").exists() for p in cache.glob("*/dependencies"))
    checks={
        "python":sys.version_info>=(3,9),
        "lxml":importlib.util.find_spec("lxml") is not None,
        "yixin_key_file":Path("~/.config/yixin-api/api-keys.json").expanduser().exists(),
        "chrome":bool(shutil.which("google-chrome") or shutil.which("chromium") or Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists()),
        "playwright_runtime":playwright,
    }
    if checks["yixin_key_file"]:
        try:
            keys=json.loads(Path("~/.config/yixin-api/api-keys.json").expanduser().read_text(encoding="utf-8"))
            checks["search_key"]=bool(keys.get("search"));checks["fin_db_key"]=bool(keys.get("fin_db"))
        except Exception:
            checks["search_key"]=False;checks["fin_db_key"]=False
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    required=("python","lxml","yixin_key_file","search_key","fin_db_key")
    missing=[name for name in required if not checks.get(name)]
    if missing:raise SystemExit("PREFLIGHT BLOCKED · "+"、".join(missing))
    if not checks["chrome"] or not checks["playwright_runtime"]:print("WARNING · Chrome或Playwright运行库缺失，HTML可生成但无法完成运行时DOM验收")
    else:print("PREFLIGHT OK")


if __name__=="__main__":main()
