#!/usr/bin/env python3
"""Small, auditable Yixin Search/Fin DB client.

Keys are loaded from the user's private mapping and are never returned, logged, or
written into a run directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

URLS = {
    "search": "https://openapi.billionsintelligence.com/api/v2/search",
    "fin_db": "https://openapi.billionsintelligence.com/api/v1/fin_db",
}
QUOTA_MESSAGE = "额度已用完，请联系销售升级：https://www.billionsintelligence.com"


class YixinError(RuntimeError):
    pass


class YixinAuthError(YixinError):
    pass


class YixinQuotaError(YixinError):
    pass


def now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def load_keys(path: Optional[Union[str, Path]] = None) -> dict[str, str]:
    config_path = Path(path or os.environ.get("YIXIN_KEY_FILE", "~/.config/yixin-api/api-keys.json")).expanduser()
    if not config_path.exists():
        raise YixinAuthError(f"缺少Yixin密钥映射：{config_path}")
    keys = json.loads(config_path.read_text(encoding="utf-8"))
    missing = [name for name in ("search", "fin_db") if not keys.get(name)]
    if missing:
        raise YixinAuthError("Yixin密钥映射缺少：" + "、".join(missing))
    return {name: str(keys[name]) for name in ("search", "fin_db")}


def payload_for(api: str, query: str, *, source: str = "web", time_range: Optional[str] = None,
                count: int = 20) -> dict[str, Any]:
    if api == "fin_db":
        return {"query": query, "data_sources": ["auto"]}
    if api == "search":
        payload: dict[str, Any] = {
            "query": query,
            "source": source,
            "search_mode": "advanced",
            "count": max(1, min(50, count)),
            "timeout": 120,
        }
        if time_range:
            payload["time_range"] = time_range
        return payload
    raise ValueError(f"未知Yixin API：{api}")


def call(api: str, query: str, key: str, *, source: str = "web", time_range: Optional[str] = None,
         count: int = 20, timeout: int = 150, retries: int = 2) -> dict[str, Any]:
    payload = payload_for(api, query, source=source, time_range=time_range, count=count)
    request = urllib.request.Request(
        URLS[api],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": key,
        },
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise YixinError("Yixin响应不是JSON对象")
                return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                raise YixinQuotaError(QUOTA_MESSAGE) from exc
            if exc.code in (401, 403):
                raise YixinAuthError(f"Yixin {api} 鉴权失败（HTTP {exc.code}），请检查API与密钥绑定") from exc
            if exc.code >= 500 and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"success": False, "error": f"HTTP {exc.code}", "body": body[:4000]}
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"success": False, "error": str(exc)}
    return {"success": False, "error": "unknown_error"}


def save_raw(raw_dir: Path, evidence_id: str, api: str, query: str, response: dict[str, Any]) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{evidence_id}-{api}.json"
    text = json.dumps(response, ensure_ascii=False, indent=2)
    (raw_dir / filename).write_text(text, encoding="utf-8")
    successful = bool(response.get("success")) and not response.get("error")
    return {
        "id": evidence_id,
        "api": api,
        "query": query,
        "retrieved_at": now_iso(),
        "raw_file": filename,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "status": "fact_source" if successful else "missing_api_error",
        "error": response.get("error"),
    }
