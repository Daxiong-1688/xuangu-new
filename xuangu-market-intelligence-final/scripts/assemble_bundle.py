#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

from workflow_lib import read_json, write_json


PROTECTED = {
    "metadata.resolved_trading_date",
    "metadata.data_source",
    "market_map.indices",
    "market_map.breadth",
    "market_map.industries",
    "evidence",
}


def deep_merge(base, patch, path=""):
    if path in PROTECTED:
        return deepcopy(base)
    if isinstance(base, dict) and isinstance(patch, dict):
        result = deepcopy(base)
        for key, value in patch.items():
            child = f"{path}.{key}" if path else key
            result[key] = deep_merge(result.get(key), value, child) if key in result else deepcopy(value)
        return result
    return deepcopy(patch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--overrides", default=None)
    args = parser.parse_args()
    run = Path(args.run).resolve()
    base = read_json(run / "analysis/baseline-bundle.json")
    if not base:
        raise SystemExit("缺少analysis/baseline-bundle.json")
    override_path = Path(args.overrides).resolve() if args.overrides else run / "analysis/analysis-overrides.json"
    overrides = read_json(override_path, {})
    bundle = deep_merge(base, overrides)
    bundle["metadata"]["analysis_mode"] = "evidence_constrained_ai" if overrides else "deterministic_baseline"
    bundle["metadata"]["validation_status"] = "pending"
    write_json(run / "bundle.json", bundle)
    print(f"BUNDLE ASSEMBLED · overrides={'yes' if overrides else 'no'}")


if __name__ == "__main__":
    main()
