#!/usr/bin/env python3
import json
from pathlib import Path

SHENWAN31 = [
    "农林牧渔", "基础化工", "钢铁", "有色金属", "电子", "汽车", "家用电器", "食品饮料",
    "纺织服饰", "轻工制造", "医药生物", "公用事业", "交通运输", "房地产", "商贸零售",
    "社会服务", "银行", "非银金融", "综合", "建筑材料", "建筑装饰", "电力设备", "机械设备",
    "国防军工", "计算机", "传媒", "通信", "煤炭", "石油石化", "环保", "美容护理"
]

def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        value = value.get("value")
        return float(value) if isinstance(value, (int, float)) else None
    return None

