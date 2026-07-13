#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from workflow_lib import SHENWAN31, read_json, write_json

INDICES = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "北证50"]


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "-", "--", "null", "None", "nan"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def response_content(response: dict) -> list[str]:
    output = []
    for item in response.get("result", []) if isinstance(response, dict) else []:
        if isinstance(item, dict) and isinstance(item.get("content"), str):
            output.append(item["content"])
    return output


def markdown_rows(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def all_rows(response: dict) -> list[dict]:
    rows = []
    for content in response_content(response):
        rows.extend(markdown_rows(content))
    return rows


def cell(row: dict, *patterns: str):
    for pattern in patterns:
        for key, value in row.items():
            if pattern.lower() in key.lower():
                return value
    return None


def raw(run: Path, evidence_id: str, api: str = "fin_db") -> dict:
    return read_json(run / "raw" / f"{evidence_id}-{api}.json", {})


def market_snapshot(run: Path, trade_date: str) -> dict:
    rows = all_rows(raw(run, "M000"))
    row = rows[0] if rows else {}
    values = {
        "up": number(cell(row, "上涨家数")),
        "down": number(cell(row, "下跌家数")),
        "flat": number(cell(row, "平盘家数")),
        "limit_up": number(cell(row, "涨停")),
        "limit_down": number(cell(row, "跌停")),
        "turnover": number(cell(row, "总成交额")),
        "previous_turnover": number(cell(row, "前一交易日总成交额", "前日总成交额")),
    }
    if values["turnover"] is not None and values["previous_turnover"] not in (None, 0):
        values["turnover_change_pct"] = (values["turnover"] / values["previous_turnover"] - 1) * 100
    else:
        values["turnover_change_pct"] = None
    complete = all(values[key] is not None for key in ("up", "down", "flat", "limit_up", "limit_down", "turnover"))
    values.update({
        "status": "fact_fin_db" if complete else "missing",
        "confidence": 0.96 if complete else 0,
        "evidence_ids": ["M000"] if rows else [],
        "as_of": trade_date,
        "missing_reason": None if complete else "Yixin Fin DB未返回完整市场宽度字段",
    })
    return values


def normalize_indices(run: Path, trade_date: str) -> list[dict]:
    output = []
    for index, name in enumerate(INDICES, 1):
        evidence_id = f"IX{index:02d}"
        rows = all_rows(raw(run, evidence_id))
        matching = [row for row in rows if name in str(row)]
        row = matching[0] if matching else (rows[0] if len(rows) == 1 else {})
        level = number(cell(row, "收盘点位", "收盘价", "收盘"))
        daily_return = number(cell(row, "涨跌幅", "当日涨跌"))
        complete = level is not None and daily_return is not None and (not row or name in str(row))
        output.append({
            "name": name,
            "level": level if complete else None,
            "return": daily_return if complete else None,
            "status": "fact_fin_db" if complete else "missing",
            "confidence": 0.93 if complete else 0,
            "evidence_ids": [evidence_id] if complete else [],
            "as_of": trade_date,
            "missing_reason": None if complete else "未取得可核验的指数名称、点位与涨跌幅组合",
        })
    return output


def normalize_industries(run: Path, trade_date: str) -> list[dict]:
    output = []
    for index, name in enumerate(SHENWAN31, 1):
        evidence_id = f"SI{index:02d}"
        group = (index - 1) // 5 + 1
        rows = all_rows(raw(run, evidence_id))
        batch_ids = [f"IG{group:02d}", f"I{group:03d}"]
        for batch_id in batch_ids:
            rows.extend(all_rows(raw(run, batch_id)))
        matching = [row for row in rows if name in str(row) and ("申万" in str(row) or "行业" in str(row))]
        row = matching[0] if matching else {}
        daily = number(cell(row, "当日涨跌幅", "涨跌幅"))
        d5 = number(cell(row, "近5日", "5日累计", "5个交易日"))
        d20 = number(cell(row, "近20日", "20日累计", "20个交易日"))
        turnover = number(cell(row, "当日成交额", "成交额"))
        complete = bool(row) and daily is not None
        output.append({
            "name": name,
            "d1": daily if complete else None,
            "d5": d5 if complete else None,
            "d20": d20 if complete else None,
            "turnover": turnover if complete else None,
            "relative_volume": None,
            "breadth_ratio": None,
            "status": "fact_fin_db" if complete else "missing",
            "confidence": 0.90 if complete and d5 is not None and d20 is not None else (0.74 if complete else 0),
            "evidence_ids": [evidence_id] + [batch_id for batch_id in batch_ids if all_rows(raw(run, batch_id))] if complete else [],
            "as_of": trade_date,
            "missing_reason": None if complete else "Yixin未返回可核验的申万一级行业指数行；未用成分股平均替代",
        })
    return output


def search_results(run: Path, evidence_id: str) -> list[dict]:
    response = raw(run, evidence_id, "search")
    output = []
    for block in response.get("result", []) if isinstance(response, dict) else []:
        content = block.get("content", []) if isinstance(block, dict) else []
        for item in content if isinstance(content, list) else []:
            if not isinstance(item, dict):
                continue
            output.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "published_at": item.get("date"),
                "source_name": (item.get("extra") or {}).get("siteName"),
                "evidence_id": evidence_id,
            })
    return output


def normalize_catalysts(run: Path, scope: list[dict]) -> dict:
    sectors = []
    for index, item in enumerate(scope, 1):
        sectors.append({
            "sector": item.get("sector"),
            "evidence_id": f"CA{index:02d}",
            "search_results": search_results(run, f"CA{index:02d}"),
            "status": "fact_search",
            "interpretation_status": "requires_ai_attribution",
        })
    return {"sectors": sectors}


def build_evidence(run: Path, trade_date: str) -> list[dict]:
    manifests = []
    for name in ("manifest.json", "individual-manifest.json", "catalyst-manifest.json", "stock-manifest.json"):
        manifests.extend(read_json(run / "raw" / name, []))
    seen = set()
    evidence = []
    for item in manifests:
        evidence_id = item.get("id")
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        evidence.append({
            "id": evidence_id,
            "field": item.get("query"),
            "status": "fact_fin_db" if item.get("api") == "fin_db" else "fact_search",
            "as_of": trade_date,
            "source": f"yixin_{item.get('api')}",
            "retrieved_at": item.get("retrieved_at"),
            "raw_file": item.get("raw_file"),
            "sha256": item.get("sha256"),
            "source_status": item.get("status"),
        })
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    run = Path(args.run).resolve()
    metadata = read_json(run / "run-metadata.json", {})
    trade_date = metadata.get("resolved_trading_date")
    if not trade_date:
        raise SystemExit("BLOCKED：run-metadata缺少resolved_trading_date")
    market = {
        "trade_date": trade_date,
        "indices": normalize_indices(run, trade_date),
        "breadth": market_snapshot(run, trade_date),
        "global_assets": {"status": "requires_ai_normalization", "search_results": search_results(run, "G001")},
    }
    industries = normalize_industries(run, trade_date)
    events = {
        "events": [],
        "candidate_sources": search_results(run, "E001"),
        "missing_reason": "未来事件须由AI逐项核对发生时间、时区和来源后写入analysis-overrides.json",
    }
    scope = read_json(run / "analysis/sector-scope.json", {}).get("selected", [])
    write_json(run / "normalized/market.json", market)
    write_json(run / "normalized/industries.json", industries)
    write_json(run / "normalized/events.json", events)
    write_json(run / "normalized/catalysts.json", normalize_catalysts(run, scope))
    if not (run / "normalized/stocks.json").exists():
        write_json(run / "normalized/stocks.json", {"stocks": [], "missing_reason": "公司数据尚未采集和核验"})
    write_json(run / "analysis/evidence.json", build_evidence(run, trade_date))
    usable = sum(item["status"] != "missing" for item in industries)
    print(json.dumps({"trade_date": trade_date, "industries_usable": usable, "industries_total": 31}, ensure_ascii=False))


if __name__ == "__main__":
    main()
