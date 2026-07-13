#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def runtime_paths():
    explicit_node = os.environ.get("XUANGU_NODE")
    explicit_modules = os.environ.get("NODE_PATH")
    if explicit_node and explicit_modules:
        return Path(explicit_node), Path(explicit_modules)
    cache = Path("~/.cache/codex-runtimes").expanduser()
    for dependencies in sorted(cache.glob("*/dependencies")):
        node = dependencies / "node/bin/node"
        modules = dependencies / "node/node_modules"
        if node.exists() and (modules / "playwright").exists():
            return node, modules
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--allow-no-browser", action="store_true")
    args = parser.parse_args()
    node, modules = runtime_paths()
    if not node:
        message = "RUNTIME INVALID · 未找到Codex Node/Playwright运行库；可设置XUANGU_NODE与NODE_PATH"
        if args.allow_no_browser:
            print(message.replace("INVALID", "SKIPPED"))
            return
        raise SystemExit(message)
    script = Path(__file__).with_suffix(".js")
    env = os.environ.copy()
    env["NODE_PATH"] = str(modules)
    subprocess.run([str(node), str(script), str(Path(args.reports).resolve()), str(Path(args.bundle).resolve())], check=True, env=env)


if __name__ == "__main__":
    main()
