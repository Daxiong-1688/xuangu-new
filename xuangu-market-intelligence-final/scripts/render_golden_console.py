#!/usr/bin/env python3
"""Render current data by mutating the golden component skeleton in place.

This renderer never clears and rebuilds an entire fixed module. It updates leaf
values and reuses every golden card, table, calendar day and interaction.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

from lxml import html

from workflow_lib import read_json


def num(value):
    return float(value) if isinstance(value, (int, float)) else None


def text(value):
    return "未核验" if value is None or value == "" else str(value)


def pct(value):
    value = num(value)
    return "未核验" if value is None else f"{'+' if value > 0 else ''}{value:.2f}%"


def integer(value):
    value = num(value)
    return "未核验" if value is None else f"{int(round(value)):,}"


def joined(values):
    values = [text(value) for value in (values or []) if value not in (None, "")]
    return "；".join(values) if values else "未核验"


def has_class(node, name):
    return name in (node.get("class") or "").split()


def descendants_by_class(node, name):
    return node.xpath(f".//*[contains(concat(' ',normalize-space(@class),' '),' {name} ')]")


def first_by_class(node, name):
    values = descendants_by_class(node, name)
    return values[0] if values else None


def set_node(node, value):
    if node is None:
        return
    node.text = text(value)


def set_cells(row, values):
    cells = row.xpath("./td")
    for cell, value in zip(cells, values):
        leaves = cell.xpath(".//*[not(*)]")
        if leaves:
            cell.text = None
            set_node(leaves[0], value)
            for extra in leaves[1:]:
                set_node(extra, "未核验")
        else:
            cell.text = text(value)


def fill_existing(nodes, data, callback, placeholder=None):
    placeholder = placeholder or {}
    for index, node in enumerate(nodes):
        callback(node, data[index] if index < len(data) else placeholder, index)


def set_width(node, value):
    if node is None:
        return
    value = max(3, min(100, num(value) or 0))
    styles = [item for item in (node.get("style") or "").split(";") if item and not item.strip().startswith("width:")]
    styles.append(f"width:{value:.0f}%")
    node.set("style", ";".join(styles))


def set_left(node, value):
    if node is None:
        return
    value = max(2, min(98, num(value) or 0))
    styles = [item for item in (node.get("style") or "").split(";") if item and not item.strip().startswith(("left:", "width:"))]
    styles.append(f"left:{value:.0f}%")
    node.set("style", ";".join(styles))


def set_sign_class(node, value, *, keep=()):
    if node is None:
        return
    classes = [item for item in (node.get("class") or "").split() if item not in {"positive", "negative", "na", "up", "down"}]
    classes.extend(item for item in keep if item not in classes)
    numeric = num(value)
    classes.append("na" if numeric is None else "positive" if numeric >= 0 else "negative")
    node.set("class", " ".join(classes))


VIEW_LABELS = {
    "relative_bullish": "相对偏多",
    "defensive": "防御占优",
    "event_watch_only": "事件观察",
    "oversold_watch_not_bottom": "超跌观察 · 未确认底部",
    "relative_bearish": "相对偏弱",
    "bullish": "偏多",
    "bearish": "偏弱",
    "watch": "等待验证",
}


def view_label(value):
    return VIEW_LABELS.get(str(value), text(value))


class GoldenRenderer:
    dynamic_ids = [
        "overview", "decision", "forecast", "macro", "signals", "breadth", "industries", "capital",
        "lifecycle", "causes", "daily", "events", "evidence", "stockEnv", "stockActions",
        "stockMapping", "stockCompare", "stockRisk", "stockFunnel", "stockPools", "stockTop",
    ]

    def __init__(self, skill_root, bundle):
        self.root = skill_root
        self.bundle = bundle
        self.market = bundle["market_map"]
        self.forecast = bundle["forecast"]
        self.pools = bundle["stock_pools"]
        self.risk = bundle["risk_audit"]
        self.trade_date = bundle["metadata"]["resolved_trading_date"]
        self.analysis_mode = bundle.get("metadata", {}).get("analysis_mode")
        self.is_formal = self.analysis_mode == "evidence_constrained_ai"
        regime = self.market.get("regime")
        self.regime_label = self.market.get("regime_label") or {
            "risk_off_deleveraging_with_defensive_rotation": "风险收缩 · 防御迁移",
            "high_level_rotation": "高位轮动",
            "risk_on": "风险偏好扩张",
            "systemic_decline": "系统性下跌",
        }.get(regime, text(regime))

    def parse(self):
        raw = (self.root / "assets/golden/market-intelligence-console.html").read_text(encoding="utf-8")
        stocks = self.pools.get("core", [])
        js_stocks = []
        for item in stocks:
            js_stocks.append({
                "name": item.get("name") or item.get("company") or item.get("code") or "未核验",
                "sector": item.get("sector") or "未核验", "chain": item.get("industry_chain") or "未核验",
                "rev": num(item.get("revenue_growth")) or 0, "profit": num(item.get("profit_growth")) or 0,
                "cash": item.get("cash_flow") or "未核验", "r5": num(item.get("r5")) or 0,
                "r20": num(item.get("r20")) or 0, "r60": num(item.get("r60")) or 0,
                "high": num(item.get("distance_from_52w_high")) or 0, "score": num(item.get("score")) or 0,
                "structure": item.get("technical") or item.get("structure") or "未核验",
                "reason": item.get("pool_reason") or item.get("reason") or "未核验",
                "risk": item.get("risk_summary") or "未核验", "color": "#315efb",
            })
        encoded = json.dumps(js_stocks, ensure_ascii=False, separators=(",", ":"))
        raw = re.sub(r"const stocks=\[.*?\];\s*const marketPage", f"const stocks={encoded};\n    const marketPage", raw, flags=re.S)
        raw = raw.replace('<td class="positive">+${s.rev.toFixed(1)}%</td><td class="positive">+${s.profit.toFixed(1)}%</td>', '<td class="${s.rev>=0?\'positive\':\'negative\'}">${s.rev>=0?\'+\':\'\'}${s.rev.toFixed(1)}%</td><td class="${s.profit>=0?\'positive\':\'negative\'}">${s.profit>=0?\'+\':\'\'}${s.profit.toFixed(1)}%</td>')
        raw = raw.replace('<b class="positive">+${s.rev.toFixed(2)}%</b>', '<b class="${s.rev>=0?\'positive\':\'negative\'}">${s.rev>=0?\'+\':\'\'}${s.rev.toFixed(2)}%</b>')
        raw = raw.replace('<b class="positive">+${s.profit.toFixed(2)}%</b>', '<b class="${s.profit>=0?\'positive\':\'negative\'}">${s.profit>=0?\'+\':\'\'}${s.profit.toFixed(2)}%</b>')
        return html.document_fromstring(raw)

    def scrub(self, doc):
        for module_id in self.dynamic_ids:
            try:
                module = doc.get_element_by_id(module_id)
            except KeyError:
                continue
            for leaf in module.xpath(".//*[not(*)]"):
                if leaf.tag in {"th", "dt", "label"}:
                    continue
                if leaf.xpath("ancestor::*[contains(concat(' ',normalize-space(@class),' '),' section-head ')]"):
                    continue
                if leaf.xpath("ancestor::*[contains(concat(' ',normalize-space(@class),' '),' legend ') or contains(concat(' ',normalize-space(@class),' '),' impact-legend ')]"):
                    continue
                if leaf.xpath("ancestor::svg"):
                    continue
                classes = (leaf.get("class") or "").split()
                if set(classes) & {"label", "eyebrow", "section-index", "state-kicker"}:
                    continue
                if leaf.text and leaf.text.strip():
                    leaf.text = "未核验"

    def global_header(self, doc):
        doc.find(".//title").text = f"玄谷市场研究控制台 · {self.trade_date}"
        brand = doc.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' brand ')]//p")
        if brand:
            brand[0].text = f"Yixin证据约束研究 · {self.trade_date}"
        pills = descendants_by_class(doc, "pill")
        if pills:
            pills[0].text = "正式 · 实时运行" if self.is_formal else "草稿 · 数据不完整"
        if len(pills) > 1:
            pills[1].text = f"风险 {self.market.get('risk_score')}/100"
        breadth = self.market.get("breadth", {})
        market_values = [
            ("MARKET REGIME", self.regime_label, "本次数据动态判断"),
            ("风险指数", self.market.get("risk_score"), "0低 · 100高"),
            ("上涨 / 下跌", f"{integer(breadth.get('up'))} / {integer(breadth.get('down'))}", "市场宽度"),
            ("涨停 / 跌停", f"{integer(breadth.get('limit_up'))} / {integer(breadth.get('limit_down'))}", "尾部风险"),
            ("成交额", f"{integer(breadth.get('turnover'))}亿", f"环比 {pct(breadth.get('turnover_change_pct'))}"),
            ("交易日", self.trade_date, "Yixin最新完成交易日"),
        ]
        self.fill_strip(doc.get_element_by_id("market"), market_values)
        self.fill_strip(doc.get_element_by_id("stocks"), [
            ("选股环境", self.pools.get("environment"), "市场→行业→公司→风险"),
            ("候选池", len(self.pools.get("candidate", [])), "行业相关与基础数据"),
            ("重点池", len(self.pools.get("watch", [])), "产业链与财务结构"),
            ("核心池", len(self.pools.get("core", [])), "关键风险完整"),
            ("正式TOP 5", "已发布" if self.pools.get("formal_top5", {}).get("published") else "未发布", "风险门槛优先"),
            ("DATA", "Yixin", "Fin DB + Search"),
        ])
        horizons=self.forecast.get("horizons",[])
        scenarios=self.forecast.get("scenarios",[])
        base=next((x for x in scenarios if text(x.get("name")) in {"基准","基准情景"}),scenarios[0] if scenarios else {})
        prediction_values=[
            ("基准情景",text(base.get("name") or "条件路径"),f"研究权重 {text(base.get('weight'))}% · 非统计概率"),
            ("预测置信度",f"{round((num(self.forecast.get('confidence')) or 0)*100)}%","条件化研究评分"),
        ]
        for index,label in enumerate(("短线方向","波段方向","中期方向")):
            item=horizons[index] if index < len(horizons) else {}
            prediction_values.append((label,item.get("direction"),item.get("period")))
        prediction_values.append(("更新机制","滚动修正",f"截至 {self.trade_date}"))
        self.fill_strip(doc.get_element_by_id("prediction"),prediction_values)

    def fill_strip(self, page, values):
        strips = [child for child in page.xpath("./div") if has_class(child, "global-strip")]
        if not strips:
            return
        items = [child for child in strips[0].xpath("./div") if has_class(child, "global-item")]
        for item, values_ in zip(items, values):
            key = first_by_class(item, "k"); val = first_by_class(item, "v"); sub = first_by_class(item, "s")
            set_node(key, values_[0]); set_node(val, values_[1]); set_node(sub, values_[2])

    def overview(self, doc):
        module = doc.get_element_by_id("overview")
        hero = first_by_class(module, "hero-main")
        set_node(hero.xpath(".//h2")[0], self.market.get("core_conclusion"))
        set_node(hero.xpath(".//p")[0], self.market.get("decision_conflict"))
        chips = descendants_by_class(hero, "chip")
        breadth = self.market.get("breadth", {})
        scope = [x for x in self.market.get("dynamic_sector_scope", []) if num(x.get("d1")) is not None]
        strongest = max(scope, key=lambda x: x["d1"], default={})
        chip_values = [
            f"【事实】上涨{integer(breadth.get('up'))} / 下跌{integer(breadth.get('down'))}",
            f"【事实】{text(strongest.get('sector'))} {pct(strongest.get('d1'))}",
            f"【推断】{text(self.market.get('fund_migration', {}).get('path'))}",
            f"【预测】{text(self.forecast.get('horizons', [{}])[0].get('direction'))}",
        ]
        for node, value in zip(chips, chip_values): set_node(node, value)
        meters = descendants_by_class(module, "meter")
        meter_title=module.xpath(".//aside[contains(concat(' ',normalize-space(@class),' '),' meters ')]/h3")
        if meter_title:set_node(meter_title[0],"市场五维状态")
        def meter(node, item, index):
            top = first_by_class(node, "meter-top")
            spans = top.xpath("./span") if top is not None else []
            bs = top.xpath("./b") if top is not None else []
            if spans: set_node(spans[0], f"{text(item.get('name'))} · {text(item.get('summary'))}")
            if bs: set_node(bs[0], f"{text(item.get('score'))} / 100")
            fills = descendants_by_class(node, "fill")
            if fills: set_width(fills[0], item.get("score"))
        fill_existing(meters, self.market.get("five_dimensions", []), meter)

    def decision(self, doc):
        module = doc.get_element_by_id("decision")
        state = first_by_class(module, "state-card")
        set_node(state.xpath(".//h3")[0], self.regime_label)
        set_node(state.xpath(".//p")[0], self.market.get("core_conclusion"))
        breadth = self.market.get("breadth", {})
        total = sum(num(breadth.get(k)) or 0 for k in ("up", "down", "flat"))
        up_ratio = (num(breadth.get("up")) or 0) / total * 100 if total else None
        scope = [x for x in self.market.get("dynamic_sector_scope", []) if num(x.get("d1")) is not None]
        weakest = min(scope, key=lambda x: x["d1"], default={})
        labels = state.xpath(".//*[contains(concat(' ',normalize-space(@class),' '),' state-labels ')]/span")
        for node, value in zip(labels, ["风险偏好扩张", "防御轮动", "系统性下跌"]): set_node(node, value)
        scale = descendants_by_class(state, "state-scale")
        if scale:
            active = 2 if (num(self.market.get("risk_score")) or 0) >= 80 else 1
            for index, node in enumerate(scale[0].xpath("./i")): node.set("class", "on" if index == active else "")
        proof = first_by_class(state, "state-proof")
        values = [
            ("未核验" if up_ratio is None else f"{up_ratio:.2f}%", "上涨占比"),
            (f"{(num(breadth.get('turnover')) or 0)/10000:.2f}万亿", "市场成交额"),
            (f"{text(weakest.get('sector'))} {pct(weakest.get('d1'))}", "最弱动态板块"),
        ]
        for box, pair in zip(proof.xpath("./div"), values):
            bs = box.xpath("./b"); spans = box.xpath("./span")
            if bs: set_node(bs[0], pair[0])
            if spans: set_node(spans[0], pair[1])
        rows = module.xpath(".//tbody/tr")
        attributions = {x.get("sector"): x for x in self.market.get("sector_attribution", [])}
        matrix = self.market.get("decision_matrix", []) or self.market.get("dynamic_sector_scope", [])
        preferred=[]
        for ranking in self.forecast.get("sector_ranking",[]):
            name=text(ranking.get("sector"))
            match=next((x for x in matrix if x.get("sector") == name or x.get("sector") in name.split("/")),None)
            if match and match not in preferred:preferred.append(match)
        matrix=preferred+[x for x in matrix if x not in preferred]
        def row(node, item, index):
            sector = item.get("sector")
            attr = attributions.get(sector, {})
            confidence = num(attr.get("confidence"))
            nature = attr.get("nature") or item.get("signal") or "/".join(item.get("selection_reasons", []))
            fund_type = "防御/降波" if sector in {"银行", "公用事业"} else ("兑现/去拥挤" if "laggard" in item.get("selection_reasons", []) else "轮动/观察")
            persistence = "中高" if confidence is not None and confidence >= .75 else "中" if confidence is not None and confidence >= .6 else "待确认"
            crowding = "高" if sector in {"电子", "有色金属", "基础化工"} else "中低"
            fundamental = text(attr.get("continuation_conditions", [None])[0] if attr.get("continuation_conditions") else "订单、盈利与价格共振")
            lifecycle = next((x.get("stage") for x in self.market.get("lifecycle", []) if sector in text(x.get("theme"))), "动态观察")
            pool = "候选观察" if any(x.get("sector") == sector for x in self.pools.get("sector_mapping", [])) else "暂不扩池"
            set_cells(node, [sector, nature, fund_type, persistence, crowding, fundamental, lifecycle, pool])
            buttons=node.xpath(".//button")
            if buttons:
                if pool=="暂不扩池":
                    buttons[0].set("onclick","return false");buttons[0].set("disabled","disabled");buttons[0].set("aria-disabled","true");buttons[0].set("style","opacity:.55;cursor:not-allowed")
                else:
                    buttons[0].attrib.pop("disabled",None);buttons[0].attrib.pop("aria-disabled",None);buttons[0].attrib.pop("style",None);buttons[0].set("onclick","openStockCenter('candidate')")
            quality=first_by_class(node,"quality-dot")
            if quality is not None:
                qclass="high" if persistence=="中高" else "mid" if persistence=="中" else "low"
                quality.set("class",f"quality-dot {qclass}")
        fill_existing(rows, matrix, row)

    def comparison(self,doc):
        market_page=doc.get_element_by_id("market")
        grids=[x for x in market_page.xpath("./div") if has_class(x,"grid2") and not x.get("id")]
        if not grids:return
        sections=grids[0].xpath("./section");scope=[x for x in self.market.get("dynamic_sector_scope",[]) if num(x.get("d1")) is not None]
        strongest=max(scope,key=lambda x:x["d1"],default={});weakest=min(scope,key=lambda x:x["d1"],default={});b=self.market.get("breadth",{})
        datasets=[
            [("市场主矛盾",self.market.get("decision_conflict"),"条件判断"),("相对强势",strongest.get("sector"),pct(strongest.get("d1"))),("相对弱势",weakest.get("sector"),pct(weakest.get("d1"))),("验证顺序",self.forecast.get("market_rhythm"),"逐级确认")],
            [("市场宽度",f"上涨{integer(b.get('up'))}家、下跌{integer(b.get('down'))}家","本次快照"),("尾部风险",f"涨停{integer(b.get('limit_up'))}家、跌停{integer(b.get('limit_down'))}家","重点观察"),("成交变化",f"成交额{integer(b.get('turnover'))}亿元，环比{pct(b.get('turnover_change_pct'))}","量价验证"),("数据边界",f"行业可靠覆盖{sum(x.get('status')!='missing' for x in self.market.get('industries',[]))}/31","缺失不补零")]
        ]
        for sec,data in zip(sections,datasets):
            src=first_by_class(sec,"src");set_node(src,self.trade_date)
            deltas=descendants_by_class(sec,"delta")
            for node,pair in zip(deltas,data):
                bs=node.xpath("./b");ps=node.xpath("./p");ems=node.xpath("./em")
                if bs:set_node(bs[0],pair[0])
                if ps:set_node(ps[0],pair[1])
                if ems:set_node(ems[0],pair[2])

    def forecast_module(self, doc):
        module = doc.get_element_by_id("forecast")
        sources=descendants_by_class(module,"src")
        if sources:set_node(sources[0],f"Yixin · {self.trade_date}")
        summary = first_by_class(module, "forecast-summary")
        h4 = summary.xpath(".//h4")
        ps = summary.xpath(".//p")
        if h4: set_node(h4[0], "基准路径")
        if ps: set_node(ps[0], self.forecast.get("base_case"))
        confidence = first_by_class(summary, "forecast-confidence")
        if confidence is not None:
            bs = confidence.xpath(".//b")
            spans = confidence.xpath(".//span")
            if bs: set_node(bs[0], f"{round((num(self.forecast.get('confidence')) or 0) * 100)}%")
            if spans: set_node(spans[0], "基准判断置信度 · 条件化研究评分")
        confidence_track=first_by_class(summary,"confidence-track")
        confidence_bar=confidence_track.xpath("./i") if confidence_track is not None else []
        if confidence_bar:set_width(confidence_bar[0],(num(self.forecast.get("confidence")) or 0)*100)
        points = first_by_class(summary, "forecast-points")
        if points is not None:
            horizons = self.forecast.get("horizons", [])
            point_data = [
                ("主要市场状态", self.regime_label),
                ("资金迁移路径", self.forecast.get("fund_path")),
                ("未来验证节奏", self.forecast.get("market_rhythm")),
                ("主要风险", joined(self.forecast.get("invalidation_signals", [])[:2])),
            ]
            for box, pair in zip(points.xpath("./div"), point_data):
                bs = box.xpath("./b"); spans = box.xpath("./span")
                if bs: set_node(bs[0], pair[0])
                if spans: set_node(spans[0], pair[1])
        horizons = descendants_by_class(module, "horizon-card")
        def horizon(node, item, index):
            top = first_by_class(node, "horizon-top")
            if top is not None:
                spans=top.xpath("./span")
                bs=top.xpath("./b")
                if spans:set_node(spans[0],["SHORT TERM","SWING","MEDIUM TERM"][index] if index < 3 else "HORIZON")
                if bs:set_node(bs[0],item.get("period"))
            h4s = node.xpath(".//h4")
            if h4s: set_node(h4s[0], item.get("style"))
            pill = first_by_class(node, "direction-pill"); set_node(pill, item.get("direction"))
            ps=node.xpath("./p")
            if ps:set_node(ps[0],"驱动："+joined(item.get("drivers")))
            items = first_by_class(node,"horizon-list").xpath("./div") if first_by_class(node,"horizon-list") is not None else []
            values = [("驱动",joined(item.get("drivers"))),("强化",joined(item.get("strengthening_signals"))),("失效",joined(item.get("invalidating_signals"))),("验证",text(item.get("next_validation")))]
            for box,pair in zip(items,values):
                bs=box.xpath("./b");spans=box.xpath("./span")
                if bs:set_node(bs[0],pair[0])
                if spans:set_node(spans[0],pair[1])
        fill_existing(horizons, self.forecast.get("horizons", []), horizon)
        factors = descendants_by_class(module, "factor")
        rankings = self.forecast.get("sector_ranking", [])
        factor_data = rankings + [{"sector": x.get("name"), "view": x.get("summary"), "confidence": (num(x.get("score")) or 50)/100} for x in self.market.get("five_dimensions", [])]
        factor_data += [{"sector":k,"view":"风险分项","confidence":(num(v) or 0)/30} for k,v in self.market.get("risk_components",{}).items()]
        def factor(node, item, index):
            top = first_by_class(node, "factor-top")
            leaves = top.xpath(".//*[not(*)]") if top is not None else []
            if leaves: set_node(leaves[0], item.get("sector"))
            if len(leaves)>1: set_node(leaves[1], round((num(item.get("confidence")) or 0)*100))
            notes=node.xpath("./small")
            if notes: set_node(notes[0], view_label(item.get("view")) if item.get("view") else item.get("action"))
            bars=descendants_by_class(node,"factor-bar")
            if bars:
                ins=bars[0].xpath(".//i")
                if ins:set_width(ins[0],(num(item.get("confidence")) or 0)*100)
        fill_existing(factors, factor_data, factor)
        paths = descendants_by_class(module, "path-card")
        def path(node,item,index):
            bs=node.xpath("./b"); ps=node.xpath(".//p"); probs=node.xpath("./strong")
            if probs:set_node(probs[0],f"{text(item.get('weight'))}%")
            if bs:set_node(bs[0],item.get("name"))
            if ps:set_node(ps[0],item.get("path"))
        fill_existing(paths,self.forecast.get("scenarios",[]),path)
        bottom=first_by_class(module,"forecast-bottom")
        if bottom is not None:
            titles=bottom.xpath("./div/h4")
            for node,value in zip(titles,["三条可能演化路径","必须推翻预测的反证"]):set_node(node,value)
        invalidates=descendants_by_class(module,"invalidate")
        invalidation_values=self.forecast.get("invalidation_signals",[])
        for index,(node,value) in enumerate(zip(invalidates,invalidation_values)):
            bs=node.xpath("./b");spans=node.xpath("./span")
            icons=node.xpath("./i")
            if icons:set_node(icons[0],"!")
            if bs:set_node(bs[0],value)
            if spans:set_node(spans[0],["风险扩散","尾部风险","流动性恶化","产业预期反证"][index] if index < 4 else "重新评估")
        disclaimers=descendants_by_class(module,"forecast-disclaimer")
        if disclaimers:set_node(disclaimers[0],"预测为条件路径与研究权重，不是收益承诺，也不声称经过历史回测。")

    def macro_signals(self, doc):
        macro=doc.get_element_by_id("macro")
        cards=descendants_by_class(macro,"macro-card")
        if not cards: cards=first_by_class(macro,"macro-grid").xpath("./div")
        macro_data=self.market.get("macro_factors",[])
        if not macro_data:
            macro_data=[
                {"name":"中国增长数据窗口","summary":"进出口、经济运行和金融统计将共同检验内需、出口与信用扩张，影响消费、银行和顺周期定价。"},
                {"name":"美国通胀与利率路径","summary":"CPI/PPI会通过美债收益率与美元影响全球高估值成长股，电子板块对这一链条更敏感。"},
                {"name":"国内政策与流动性","summary":"货币政策执行和金融统计决定风险偏好能否从防御迁移回成长，需结合成交和市场宽度验证。"},
                {"name":"大型申购资金扰动","summary":"长鑫科技申购窗口可能造成短期资金占用；若成交继续收缩，题材与高波动板块承压更明显。"},
            ]
        def mcard(node,item,index):
            h4=node.xpath(".//h4"); ps=node.xpath(".//p");icons=descendants_by_class(node,"icon")
            if icons:set_node(icons[0],["GLOBAL","RATES","POLICY","EVENT"][index%4])
            if h4:set_node(h4[0],item.get("name"))
            if ps:set_node(ps[0],item.get("summary"))
        fill_existing(cards,macro_data,mcard)
        transmission=first_by_class(macro,"transmission")
        if transmission is not None:
            nodes=transmission.xpath("./span")
            values=["中国/美国宏观数据","利率与汇率预期","全球成长估值","A股风格与行业轮动","A股风险偏好"]
            for node,value in zip(nodes,values):set_node(node,value)
            for node in transmission.xpath("./i"):set_node(node,"→")
        signals=doc.get_element_by_id("signals")
        cards=descendants_by_class(signals,"signal")
        def scard(node,item,index):
            h4=node.xpath(".//h4");ps=node.xpath(".//p");lights=descendants_by_class(node,"light")
            if h4:set_node(h4[0],item.get("name"))
            if ps:set_node(ps[0],item.get("summary"))
            if lights:
                color={"red":"#d65757","amber":"#e7a43a","green":"#59ad7d"}.get(item.get("level"),"#e7a43a");lights[0].set("style",f"background:{color}")
        signal_data=self.market.get("signals",[]) or [
            {"name":f"{x.get('name')} · {'红色' if x.get('color') == 'red' else '黄色' if x.get('color') == 'amber' else '绿色'}","summary":x.get("summary"),"level":x.get("color")}
            for x in self.market.get("five_dimensions",[])
        ]
        fill_existing(cards,signal_data,scard)

    def breadth_industries(self, doc):
        breadth=self.market.get("breadth",{})
        module=doc.get_element_by_id("breadth")
        cards=descendants_by_class(module,"index-card")
        def index_card(node,item,index):
            value_node=first_by_class(node,"value")
            set_node(first_by_class(node,"name"),item.get("name"));set_node(value_node,pct(item.get("return")));set_sign_class(value_node,item.get("return"),keep=("value",))
        fill_existing(cards,self.market.get("indices",[]),index_card)
        stats=descendants_by_class(module,"stat")
        values=[breadth.get("up"),breadth.get("down"),breadth.get("limit_up"),breadth.get("limit_down")]
        for node,value in zip(stats,values):
            nums=descendants_by_class(node,"num")
            if nums:set_node(nums[0],integer(value))
        bars=descendants_by_class(module,"breadthbar")
        total=sum(num(breadth.get(k)) or 0 for k in ("up","down","flat"));up=(num(breadth.get("up")) or 0)
        if bars:
            parts=bars[0].xpath("./div");ratio=up/total*100 if total else 0
            if parts:set_width(parts[0],ratio);set_node(parts[0],f"{ratio:.1f}%")
            if len(parts)>1:set_node(parts[1],f"{100-ratio:.1f}%")
        notices=descendants_by_class(module,"notice")
        if notices:set_node(notices[-1],f"成交额 {integer(breadth.get('turnover'))}亿元，较前日 {pct(breadth.get('turnover_change_pct'))}。")
        industry_module=doc.get_element_by_id("industries")
        rows=industry_module.xpath(".//tbody/tr")
        inds=self.market.get("industries",[])
        def industry_row(node,item,index):
            status="高" if item.get("status")!="missing" and (num(item.get("confidence")) or 0)>=.8 else ("中" if item.get("status")!="missing" else "未核验")
            nature="上涨" if (num(item.get("d1")) or -999)>=0 else "下跌" if num(item.get("d1")) is not None else "数据缺失"
            set_cells(node,[item.get("name"),pct(item.get("d1")),pct(item.get("d5")),pct(item.get("d20")),nature,status])
            cells=node.xpath("./td")
            for cell,key in zip(cells[1:4],("d1","d5","d20")):set_sign_class(cell,item.get(key))
        fill_existing(rows,inds,industry_row)
        market_page=doc.get_element_by_id("market")
        heat_sections=[x for x in market_page.xpath("./section") if x.get("id") is None and "行业成交热力图" in x.text_content()]
        if heat_sections:
            tiles=descendants_by_class(heat_sections[0],"tile")
            ranked=sorted([x for x in inds if num(x.get("turnover")) is not None],key=lambda x:x["turnover"],reverse=True)
            def tile(node,item,index):
                bs=node.xpath("./b");spans=node.xpath("./span")
                if bs:set_node(bs[0],item.get("name"))
                if spans:set_node(spans[-1],f"{pct(item.get('d1'))} · {integer(item.get('turnover'))}亿")
                phase=first_by_class(node,"phase");set_node(phase,"相对强势" if (num(item.get("d1")) or -999)>=0 else "承压")
                classes=[x for x in (node.get("class") or "").split() if x not in {"up","down","flat"}]
                classes.append("flat" if num(item.get("d1")) is None else "up" if item["d1"]>=0 else "down");node.set("class"," ".join(classes))
            fill_existing(tiles,ranked,tile)
            legends=descendants_by_class(heat_sections[0],"legend")
            if legends:
                spans=legends[0].xpath("./span")
                if spans:set_node(spans[-1],f"本次可靠行业覆盖 {sum(x.get('status')!='missing' for x in inds)}/31；缺失行业不伪造热度")

    def capital_lifecycle(self,doc):
        module=doc.get_element_by_id("capital");scope=self.market.get("dynamic_sector_scope",[])
        weak=[x.get("sector") for x in sorted(scope,key=lambda x:num(x.get("d1")) if num(x.get("d1")) is not None else 999) if num(x.get("d1")) is not None and x["d1"]<0]
        strong=[x.get("sector") for x in sorted(scope,key=lambda x:num(x.get("d1")) if num(x.get("d1")) is not None else -999,reverse=True) if num(x.get("d1")) is not None and x["d1"]>=0]
        sources=descendants_by_class(module,"source");targets=descendants_by_class(module,"target")
        source_values=weak[:2] or ["高波动与拥挤方向","弱趋势方向"]
        target_values=(strong+["高股息/低波动","现金与防御仓位","基本面可验证方向"])[:4]
        for index,node in enumerate(sources):
            set_node(node,source_values[index] if index < len(source_values) else "风险预算收缩方向")
            smalls=node.xpath("./small")
            if smalls:set_node(smalls[0],"量价转弱与风险预算下降")
        for index,node in enumerate(targets):set_node(node,target_values[index] if index < len(target_values) else "等待验证方向")
        arrows=descendants_by_class(module,"arrow")
        for node,value in zip(arrows,["降低波动","防御迁移","现金承接","事件观察"]):
            spans=node.xpath("./span")
            if spans:set_node(spans[0],value)
        rows=module.xpath(".//tbody/tr")
        def trend_row(node,item,index):
            set_cells(node,[item.get("sector"),pct(item.get("d1")),pct(item.get("d5")),pct(item.get("d20")),item.get("signal") or "动态观察"])
            cells=node.xpath("./td")
            for cell,key in zip(cells[1:4],("d1","d5","d20")):set_sign_class(cell,item.get(key))
        fill_existing(rows,scope,trend_row)
        life=doc.get_element_by_id("lifecycle");rows=descendants_by_class(life,"life-row")
        life_data=self.market.get("lifecycle",[])
        def life_row(node,item,index):
            bs=node.xpath("./b");spans=node.xpath("./span")
            if bs:set_node(bs[0],item.get("theme"))
            if spans:set_node(spans[-1],item.get("stage"))
            ins=node.xpath(".//i");
            if ins:set_left(ins[0],20+index*14)
        fallback=[{"theme":"待形成新主线","stage":"潜伏观察期"},{"theme":"高波动题材","stage":"退潮验证期"}]
        fill_existing(rows,life_data+fallback,life_row)
        foot=descendants_by_class(life,"footnote")
        if foot:set_node(foot[0],"生命周期位置基于涨跌、趋势、成交和催化推断，必须由后续价格、订单和业绩验证。")

    def causes(self,doc):
        module=doc.get_element_by_id("causes");cards=descendants_by_class(module,"cause-pro")
        attrs=self.market.get("sector_attribution",[])
        preferred=[]
        for ranking in self.forecast.get("sector_ranking",[]):
            parts=text(ranking.get("sector")).split("/")
            match=next((x for x in attrs if x.get("sector") in parts or x.get("sector")==ranking.get("sector")),None)
            if match and match not in preferred:preferred.append(match)
        attrs=preferred+[x for x in attrs if x not in preferred]
        def cause(node,item,index):
            facts=item.get("facts",{})
            h4=node.xpath(".//h4");smalls=node.xpath(".//small");badges=descendants_by_class(node,"badge")
            if h4:set_node(h4[0],item.get("sector"))
            if smalls:set_node(smalls[0],f"20日 {pct(facts.get('d20'))} · 5日 {pct(facts.get('d5'))}")
            if badges:set_node(badges[0],item.get("nature"))
            ret=first_by_class(node,"cause-return")
            if ret is not None:
                ret.text=pct(facts.get("d1"));set_sign_class(ret,facts.get("d1"),keep=("cause-return",));cs=ret.xpath("./small")
                turnover=facts.get("turnover")
                if cs:set_node(cs[0],f"成交 {integer(turnover)}亿" if num(turnover) is not None else "成交额未核验")
            summary=first_by_class(node,"cause-summary");set_node(summary,item.get("primary_reason")+"。"+joined(item.get("secondary_reasons")) if item.get("primary_reason") else None)
            drivers=descendants_by_class(node,"driver")
            driver_data=[("价格与筹码",.9),("资金结构",.7),("事件催化",item.get("confidence")),("基本面确认",.5)]
            for driver,pair in zip(drivers,driver_data):
                labels=driver.xpath(".//label");strongs=driver.xpath(".//strong");ins=driver.xpath(".//i")
                if labels:set_node(labels[0],pair[0])
                if strongs:set_node(strongs[0],round((num(pair[1]) or 0)*100))
                if ins:set_width(ins[0],(num(pair[1]) or 0)*100)
            boxes=descendants_by_class(node,"cause-box")
            box_data=[("主因",item.get("primary_reason")),("产业传导",item.get("industry_transmission")),("持续条件",joined(item.get("continuation_conditions"))),("反证信号",joined(item.get("invalidating_signals")))]
            for box,pair in zip(boxes,box_data):
                bs=box.xpath("./b");ps=box.xpath("./p")
                if bs:set_node(bs[0],pair[0])
                if ps:set_node(ps[0],pair[1])
            verdict=first_by_class(node,"cause-verdict")
            if verdict is not None:
                spans=verdict.xpath("./span")
                if spans:set_node(spans[0],f"判断：{text(item.get('nature'))}")
                if len(spans)>1:set_node(spans[1],f"证据：{round((num(item.get('confidence')) or 0)*100)} · {joined(item.get('evidence_ids'))}")
        fill_existing(cards,attrs,cause)

    def daily_events_evidence(self,doc):
        daily=doc.get_element_by_id("daily");items=descendants_by_class(daily,"watch-item")
        daily_values=self.market.get("daily_validation",[])+self.forecast.get("invalidation_signals",[])
        daily_labels=["尾部风险","市场宽度","科技止跌","防御有效性","成交承接","防御补跌","跌停扩散","量价恶化","产业反证"]
        daily_triggers=["风险下降","宽度修复","观察企稳","验证轮动","看量能","风险升级","风险升级","风险升级","推翻逻辑"]
        watch_cards=descendants_by_class(daily,"watch-card")
        for node,value in zip(watch_cards,["市场是否停止风险扩散","资金迁移是否形成有效承接","当前预测何时需要推翻"]):
            h4=node.xpath("./h4")
            if h4:set_node(h4[0],value)
        for index,(node,value) in enumerate(zip(items,daily_values)):
            nums=descendants_by_class(node,"watch-num");bs=node.xpath(".//b");ps=node.xpath(".//p");triggers=descendants_by_class(node,"trigger")
            if nums:set_node(nums[0],index%3+1)
            if bs:set_node(bs[0],daily_labels[index] if index < len(daily_labels) else "动态验证")
            if ps:set_node(ps[0],value)
            if triggers:set_node(triggers[0],daily_triggers[index] if index < len(daily_triggers) else "待验证")
        workflow=first_by_class(daily,"workflow-link")
        if workflow is not None:
            bs=workflow.xpath(".//b");ps=workflow.xpath(".//p");buttons=workflow.xpath(".//button")
            if bs:set_node(bs[0],"从市场地图进入选股决策链")
            if ps:set_node(ps[0],"市场状态 → 板块归因 → 公司质量 → 技术结构 → 风险门槛")
            if buttons:set_node(buttons[0],"进入选股中心 →")
        events_module=doc.get_element_by_id("events")
        src=descendants_by_class(events_module,"src")
        if src:set_node(src[0],f"Yixin · {self.trade_date}")
        events=self.market.get("events",[])
        day_cards=descendants_by_class(events_module,"day-card")
        try:start=date.fromisoformat(self.trade_date)
        except Exception:start=date.today()
        first_day=start+timedelta(days=1);last_day=start+timedelta(days=7)
        section_ps=events_module.xpath("./div[contains(concat(' ',normalize-space(@class),' '),' section-head ')]/div/p")
        if section_ps:set_node(section_ps[0],f"{first_day.year}年{first_day.month}月{first_day.day}日—{last_day.month}月{last_day.day}日 · 时间以北京时间为主；事件时点可能调整")
        weekdays="一二三四五六日"
        for index,day in enumerate(day_cards):
            day_date=start+timedelta(days=index+1)
            time_nodes=day.xpath(".//time");
            if time_nodes:set_node(time_nodes[0],day_date.strftime("%m/%d"))
            spans=first_by_class(day,"day-date").xpath("./span") if first_by_class(day,"day-date") is not None else []
            if spans:set_node(spans[0],f"周{weekdays[day_date.weekday()]} · 北京时间")
            heat=first_by_class(day,"heat")
            if heat is not None:set_node(heat,"滚动监测")
        event_cards=descendants_by_class(events_module,"calendar-event")
        def event_card(node,item,index):
            bs=node.xpath(".//b");times=descendants_by_class(node,"event-time");ps=node.xpath(".//p")
            if bs:set_node(bs[0],item.get("event"))
            if times:set_node(times[0],item.get("datetime"))
            evidence_suffix=f"；证据：{joined(item.get('evidence_ids'))}" if item.get("evidence_ids") else ""
            if ps:set_node(ps[0],item.get("summary") or f"来源状态：{text(item.get('verification_status'))}；重要性：{text(item.get('importance'))}{evidence_suffix}")
            importance=str(item.get("importance") or "").lower()
            classes=[x for x in (node.get("class") or "").split() if x not in {"market-critical","market-medium","theme-catalyst"}]
            if importance in {"critical","high"}:classes.append("market-critical")
            elif importance in {"medium"}:classes.append("market-medium")
            elif importance not in {"monitor","missing"}:classes.append("theme-catalyst")
            node.set("class"," ".join(classes))
            impacts_label=descendants_by_class(node,"market-impact")
            if impacts_label:set_node(impacts_label[0],"强影响" if importance in {"high","critical"} else "中等影响" if importance=="medium" else "滚动监测")
            dots=descendants_by_class(node,"importance")
            if dots:
                on_count=5 if importance in {"critical","high"} else 3 if importance=="medium" else 1
                for dot_index,dot in enumerate(dots[0].xpath("./i")):dot.set("class","on" if dot_index<on_count else "")
            impacts=first_by_class(node,"impact-line")
            if impacts is not None:
                channels=item.get("impact_channels") or (["日程更新","突发事件","财报公告","继续核验"] if importance in {"monitor","missing"} else ["风险偏好","利率/汇率","行业轮动","待验证"])
                for span,value in zip(impacts.xpath("./span"),channels):set_node(span,value)
            node.set("style","")
        for node in event_cards:node.set("style","display:none")
        buckets={}
        for item in events:
            dates=re.findall(r"\d{4}-\d{2}-\d{2}",text(item.get("datetime")))
            key=dates[0] if dates else None
            buckets.setdefault(key,[]).append(item)
        used=set()
        for day_index,day in enumerate(day_cards):
            day_date=(start+timedelta(days=day_index+1)).isoformat()
            slots=descendants_by_class(day,"calendar-event")
            day_events=buckets.get(day_date,[])
            for slot_index,(slot,item) in enumerate(zip(slots,day_events)):
                event_card(slot,item,slot_index);used.add(id(item))
            heat=first_by_class(day,"heat")
            if heat is not None:set_node(heat,"重点" if any(str(x.get('importance')).lower() in {'high','critical'} for x in day_events) else "观察")
            if not day_events and slots:
                event_card(slots[0],{"event":"暂无已核验高影响事件","datetime":day_date,"summary":"截至本次运行，Yixin未返回该日已核验的高影响日程；继续监测公告、财报和突发事件。","importance":"monitor","verification_status":"missing","impact_channels":["日程更新","突发事件","财报公告","继续核验"]},0)
        remaining=[item for item in events if id(item) not in used]
        free=[node for node in event_cards if (node.get("style") or "").replace(" ","")=="display:none"]
        for index,(slot,item) in enumerate(zip(free,remaining)):event_card(slot,item,index)
        summary=first_by_class(events_module,"calendar-summary")
        if summary is not None:
            boxes=summary.xpath("./div")
            high_dates=sorted({m.group(0)[5:] for x in events if str(x.get("importance")).lower() in {"high","critical"} for m in [re.search(r"\d{4}-\d{2}-\d{2}",text(x.get("datetime")))] if m})
            wave="、".join(x.replace("-","/") for x in high_dates[:3]) if high_dates else "待核验"
            vals=[(f"{len(events)}个","已核验事件"),(f"{sum(str(x.get('importance')).lower() in {'high','critical'} for x in events)}个","高重要性事件"),("7天","滚动验证窗口"),(wave,"潜在波动集中期")]
            for box,pair in zip(boxes,vals):
                bs=box.xpath("./b");spans=box.xpath("./span")
                if bs:set_node(bs[0],pair[0])
                if spans:set_node(spans[0],pair[1])
        notes=descendants_by_class(events_module,"calendar-note")
        if notes:
            bs=notes[0].xpath("./b");notes[0].text=None
            if bs:
                set_node(bs[0],"本周关键传导链：")
                bs[0].tail="只把已核验时间和来源的事件列为确定日程；其余候选保留在证据缺口，不伪造具体时点。"
        scenarios=events_module.xpath("./div[contains(concat(' ',normalize-space(@class),' '),' grid3 ')]/*")
        def scen(node,item,index):
            probs=descendants_by_class(node,"prob");h4=node.xpath(".//h4");ps=node.xpath(".//p")
            if probs:set_node(probs[0],f"{text(item.get('weight'))}%")
            if h4:set_node(h4[0],item.get("name"))
            if ps:set_node(ps[0],item.get("path"))
        fill_existing(scenarios,self.forecast.get("scenarios",[]),scen)
        evidence=doc.get_element_by_id("evidence");evcards=descendants_by_class(evidence,"evidence-card")
        evdata=[("【事实】直接数据",f"市场宽度、指数和{sum(x.get('status')!='missing' for x in self.market.get('industries',[]))}/31行业来自本次Yixin数据。"),("【推断】分析结论",self.market.get("fund_migration",{}).get("meaning") or self.market.get("fund_migration",{}).get("path")),("【预测】条件情景",self.forecast.get("base_case"))]
        for node,pair in zip(evcards,evdata):
            bs=node.xpath(".//b");ps=node.xpath(".//p")
            if bs:set_node(bs[0],pair[0])
            if ps:set_node(ps[0],pair[1])
        subheads=evidence.xpath(".//h4")
        for node,value in zip(subheads,["当前数据缺口","今天不要被这些现象误导"]):set_node(node,value)
        data_states=descendants_by_class(evidence,"data-state")
        gaps=self.market.get("data_gaps",[])
        for node,value in zip(data_states,gaps):
            bs=node.xpath(".//b");sp=node.xpath(".//span")
            if bs:set_node(bs[0],f"缺口 {data_states.index(node)+1}")
            if sp:set_node(sp[0],value)
        warnings=descendants_by_class(evidence,"warning-item")
        warnvalues=["指数涨跌不能替代市场宽度。","成交放大可能同时包含买入和兑现。","新闻存在不等于新闻导致涨跌。","资金迁移是量价推断，不是账户穿透。"]
        warning_pairs=[
            ("指数涨跌 ≠ 个股体验",warnvalues[0]),
            ("成交变化 ≠ 单向资金流",warnvalues[1]),
            ("新闻存在 ≠ 形成因果",warnvalues[2]),
            ("资金迁移 ≠ 账户穿透",warnvalues[3]),
        ]
        for node,pair in zip(warnings,warning_pairs):
            bs=node.xpath("./b")
            node.text=None
            if bs:
                set_node(bs[0],pair[0]);bs[0].tail="\n"+pair[1]

    def prediction_page(self,doc):
        page=doc.get_element_by_id("prediction")
        horizons=self.forecast.get("horizons",[])
        rankings=list(self.forecast.get("sector_ranking",[]))
        scope=self.market.get("dynamic_sector_scope",[])
        attrs=self.market.get("sector_attribution",[])

        framework=next((x for x in page.xpath("./section") if "预测不是猜点位" in x.text_content()),None)
        if framework is not None:
            src=descendants_by_class(framework,"src")
            if src:set_node(src[0],f"独立研究页面 · {self.trade_date}")

        direction=next((x for x in page.xpath("./section") if "未来方向一页结论" in x.text_content()),None)
        if direction is not None:
            src=descendants_by_class(direction,"src")
            if src:set_node(src[0],f"基准情景 · {round((num(self.forecast.get('confidence')) or 0)*100)}%研究置信度")
            boxes=descendants_by_class(direction,"direction-box")
            top_names="、".join(text(x.get("sector")) for x in rankings[:2]) or "未核验"
            wait_item=next((x for x in rankings if str(x.get("view")) in {"event_watch_only","oversold_watch_not_bottom","watch"}),{})
            weak_item=next((x for x in rankings if str(x.get("view")) in {"relative_bearish","bearish"}),rankings[-1] if rankings else {})
            short=horizons[0] if horizons else {}
            direction_data=[
                ("大盘方向",short.get("direction"),short.get("period")),
                ("市场风格",short.get("style"),"由市场宽度与风险预算共同决定"),
                ("资金性质","防御迁移 / 风险收缩",self.forecast.get("fund_path")),
                ("相对优先",top_names,"仅代表相对强弱，不直接升级股票池"),
                ("等待验证",wait_item.get("sector") or "事件方向",view_label(wait_item.get("view"))),
                ("短线承压",weak_item.get("sector") or "高波动方向",view_label(weak_item.get("view"))),
            ]
            for box,item in zip(boxes,direction_data):
                spans=box.xpath("./span");bs=box.xpath("./b");smalls=box.xpath("./small")
                if spans:set_node(spans[0],item[0])
                if bs:set_node(bs[0],item[1])
                if smalls:set_node(smalls[0],item[2])

        rank_section=next((x for x in page.xpath("./section") if "板块预测排行榜" in x.text_content()),None)
        if rank_section is not None:
            src=descendants_by_class(rank_section,"src")
            if src:set_node(src[0],f"相对强弱预测 · {self.trade_date}")
            existing={text(x.get("sector")) for x in rankings}
            existing_parts={part for name in existing for part in name.split("/")}
            for item in scope:
                sector=text(item.get("sector"))
                if sector in existing or sector in existing_parts:continue
                d1=num(item.get("d1"));z=abs(num(item.get("zscore_1d")) or 0)
                rankings.append({"sector":sector,"view":"relative_bullish" if d1 is not None and d1>=0 else "relative_bearish","confidence":min(.78,.5+z*.1),"scope_item":item})
                existing.add(sector)
            rows=rank_section.xpath(".//tbody/tr")
            def rank_row(node,item,index):
                sector=text(item.get("sector"));parts=sector.split("/")
                attr=next((x for x in attrs if x.get("sector")==sector or x.get("sector") in parts),{})
                view=str(item.get("view") or "watch")
                if not horizons:horizon={}
                elif view in {"relative_bearish","bearish","oversold_watch_not_bottom"}:horizon=horizons[0]
                else:horizon=horizons[min(1,len(horizons)-1)]
                core=attr.get("primary_reason") or f"当日{pct((item.get('scope_item') or {}).get('d1'))}；等待价格、成交与催化共振"
                conditions=joined(attr.get("continuation_conditions") or horizon.get("conditions"))
                strengthening=joined((attr.get("continuation_conditions") or [])[1:2] or horizon.get("strengthening_signals"))
                invalidating=joined(attr.get("invalidating_signals") or horizon.get("invalidating_signals"))
                confidence=round((num(item.get("confidence")) or 0)*100)
                set_cells(node,[f"{index+1:02d}",sector,view_label(view),horizon.get("period"),core,conditions,strengthening,invalidating,confidence])
                cells=node.xpath("./td")
                if len(cells)>2:
                    bias=first_by_class(cells[2],"bias")
                    if bias is not None:
                        bias_class="bull" if view in {"relative_bullish","bullish","defensive"} else "bear" if view in {"relative_bearish","bearish"} else "event" if view=="event_watch_only" else "watch"
                        bias.set("class",f"bias {bias_class}")
                if len(cells)>8:
                    mini=first_by_class(cells[8],"confidence-mini")
                    if mini is not None:
                        bars=mini.xpath("./i");spans=mini.xpath("./span")
                        if bars:bars[0].text=None;bars[0].set("style",f"--confidence:{confidence}%")
                        if spans:set_node(spans[0],confidence)
            fill_existing(rows,rankings,rank_row)
            for node in rows[len(rankings):]:node.set("style","display:none")
            disclaimers=descendants_by_class(rank_section,"forecast-disclaimer")
            if disclaimers:set_node(disclaimers[0],"板块预测表示相对强弱和条件路径，不保证绝对涨跌；任何方向都必须经过后续价格、成交、订单和盈利验证。")

        fund_section=next((x for x in page.xpath("./div/section") if "资金去向预测" in x.text_content()),None)
        if fund_section is not None:
            sources=descendants_by_class(fund_section,"flow-source")
            targets=descendants_by_class(fund_section,"flow-target")
            weak=sorted([x for x in scope if num(x.get("d1")) is not None],key=lambda x:x["d1"])
            source_values=[f"{x.get('sector')} · {pct(x.get('d1'))}" for x in weak[:3]]
            target_values=[f"{view_label(x.get('view'))}：{x.get('sector')}" for x in rankings[:3]]
            for index,node in enumerate(sources):set_node(node,source_values[index] if index<len(source_values) else "风险预算下降方向")
            for index,node in enumerate(targets):set_node(node,target_values[index] if index<len(target_values) else "等待验证方向")
            bridge=first_by_class(fund_section,"flow-bridge")
            if bridge is not None:
                spans=bridge.xpath("./span");icons=bridge.xpath("./i")
                if spans:set_node(spans[0],"风险释放")
                if len(spans)>1:set_node(spans[1],"再配置")
                if icons:set_node(icons[0],"→")
            summary=first_by_class(fund_section,"capital-summary")
            if summary is not None:
                bs=summary.xpath("./b");summary.text=None
                if bs:set_node(bs[0],"关键预测：");bs[0].tail=text(self.forecast.get("fund_path"))+"。"+text(self.forecast.get("market_rhythm"))

        rule_section=next((x for x in page.xpath("./div/section") if "方向进入选股中心的门槛" in x.text_content()),None)
        if rule_section is not None:
            workflow=first_by_class(rule_section,"workflow-link")
            if workflow is not None:
                bs=workflow.xpath(".//b");ps=workflow.xpath(".//p");buttons=workflow.xpath(".//button")
                mapping=self.pools.get("sector_mapping",[])
                if bs:set_node(bs[0],"当前预测映射")
                if ps:set_node(ps[0],"；".join(f"{text(x.get('sector'))}：{text(x.get('role'))}" for x in mapping) or "公司级数据不足，暂不形成正式映射")
                target_pool="watch" if self.pools.get("watch") else "candidate"
                if buttons:set_node(buttons[0],"查看重点池 →" if target_pool=="watch" else "查看候选池 →");buttons[0].set("onclick",f"openStockCenter('{target_pool}')")

        rhythm_section=next((x for x in page.xpath("./section") if "未来市场节奏预测" in x.text_content()),None)
        if rhythm_section is not None:
            src=descendants_by_class(rhythm_section,"src")
            try:last_day=date.fromisoformat(self.trade_date)+timedelta(days=7)
            except Exception:last_day=date.today()+timedelta(days=7)
            if src:set_node(src[0],f"{self.trade_date} → {last_day.isoformat()}")
            rhythm_data=[("当前基准","先确认风险是否收敛",self.forecast.get("base_case"))]
            rhythm_data += [(x.get("period"),x.get("direction"),"驱动："+joined(x.get("drivers"))) for x in horizons[:3]]
            rhythm_data.append(("反证触发","重新评估全部方向",joined(self.forecast.get("invalidation_signals"))))
            cards=descendants_by_class(rhythm_section,"rhythm-card")
            for card,item in zip(cards,rhythm_data):
                times=card.xpath("./time");bs=card.xpath("./b");ps=card.xpath("./p")
                if times:set_node(times[0],item[0])
                if bs:set_node(bs[0],item[1])
                if ps:set_node(ps[0],item[2])

        collaboration=next((x for x in page.xpath("./section") if "三页面如何协同" in x.text_content()),None)
        if collaboration is not None:
            workflow=first_by_class(collaboration,"workflow-link")
            if workflow is not None:
                bs=workflow.xpath(".//b");ps=workflow.xpath(".//p");buttons=workflow.xpath(".//button")
                if bs:set_node(bs[0],"预测成立且风险字段完整时才升级股票池")
                if ps:set_node(ps[0],"产业趋势、公司质量、资金结构和价格位置至少两项共振；反证触发时立即降级。")
                if buttons:buttons[0].set("onclick","openStockCenter('candidate')")

    def stocks(self,doc):
        mapping=self.pools.get("sector_mapping",[]);candidate=self.pools.get("candidate",[]);watch=self.pools.get("watch",[]);core=self.pools.get("core",[])
        env=doc.get_element_by_id("stockEnv");cards=first_by_class(env,"stock-environment").xpath("./div")
        top_ranks=self.forecast.get("sector_ranking",[])
        envdata=[
            {"label":"当前策略","sector":"先控风险，再做结构研究","role":f"市场风险指数{self.market.get('risk_score')}；优先等待尾部风险与市场宽度修复。"},
            {"label":"相对优先","sector":"、".join(text(x.get("sector")) for x in top_ranks[:2]),"role":"只进入候选观察，不因板块相对强势直接升级公司。"},
            {"label":"事件方向","sector":text(mapping[2].get("sector") if len(mapping)>2 else "未来事件映射"),"role":text(mapping[2].get("role") if len(mapping)>2 else "等待催化、价格与基本面共振")},
            {"label":"等待方向","sector":text(mapping[1].get("sector") if len(mapping)>1 else "高波动成长"),"role":text(mapping[1].get("role") if len(mapping)>1 else "等待缩量止跌与趋势修复")},
            {"label":"选股约束","sector":"正式TOP 5暂不发布" if not self.pools.get("formal_top5",{}).get("published") else "正式TOP 5已发布","role":self.pools.get("formal_top5",{}).get("reason")},
        ]
        def envcard(node,item,index):
            spans=node.xpath(".//span");bs=node.xpath(".//b");ps=node.xpath(".//p")
            if spans:set_node(spans[0],item.get("label") or "动态方向")
            if bs:set_node(bs[0],item.get("sector"))
            if ps:set_node(ps[0],item.get("role"))
        fill_existing(cards,envdata,envcard)
        actions=doc.get_element_by_id("stockActions");acards=first_by_class(actions,"action-board").xpath("./article")
        action_data=[
            {"label":"优先验证","sector":"市场宽度与跌停收敛","role":"先确认风险不再扩散，再提高候选池研究强度。"},
            {"label":"重点跟踪","sector":text(mapping[0].get("sector") if mapping else "相对强势板块"),"role":text(mapping[0].get("role") if mapping else "等待价格与基本面验证")},
            {"label":"等待企稳","sector":text(mapping[1].get("sector") if len(mapping)>1 else "高波动板块"),"role":text(mapping[1].get("role") if len(mapping)>1 else "不抢反弹，等待技术结构修复")},
            {"label":"事件观察","sector":text(mapping[2].get("sector") if len(mapping)>2 else "事件映射方向"),"role":text(mapping[2].get("role") if len(mapping)>2 else "只保留可验证的产业映射")},
            {"label":"风险门槛","sector":"关闭核心池与正式TOP 5" if not self.risk.get("critical_complete") else "允许进入核心池审核","role":self.pools.get("formal_top5",{}).get("reason")},
        ]
        def actioncard(node,item,index):
            labels=descendants_by_class(node,"action-label");h4=node.xpath(".//h4");ps=node.xpath(".//p")
            if labels:set_node(labels[0],item.get("label") or "动态研究")
            if h4:set_node(h4[0],item.get("sector"))
            if ps:set_node(ps[0],item.get("role"))
        fill_existing(acards,action_data,actioncard)
        smap=doc.get_element_by_id("stockMapping");rows=smap.xpath(".//tbody/tr")
        def maprow(node,item,index):set_cells(node,[item.get("sector"),"动态周期","证据约束","候选/重点","等待验证",next((x.get("name") for x in candidate if x.get("sector")==item.get("sector")),"未发布"),"反证触发则降级"])
        fill_existing(rows,mapping,maprow)
        for node in rows[len(mapping):]:node.set("style","display:none")
        compare=doc.get_element_by_id("stockCompare");rows=compare.xpath(".//tbody/tr");comparison=self.pools.get("company_comparison",[]) or core
        def comparerow(node,item,index):
            set_cells(node,[item.get("name") or item.get("company"),item.get("sector"),item.get("industry_chain"),pct(item.get("revenue_growth")),pct(item.get("profit_growth")),item.get("cash_flow"),pct(item.get("r20")),pct(item.get("r60")),item.get("technical"),item.get("risk_summary"),item.get("score")])
            cells=node.xpath("./td")
            for cell,key in ((cells[3],"revenue_growth"),(cells[4],"profit_growth"),(cells[6],"r20"),(cells[7],"r60")):set_sign_class(cell,item.get(key))
        if comparison:
            fill_existing(rows,comparison,comparerow)
            for node in rows[len(comparison):]:node.set("style","display:none")
        elif rows:
            set_cells(rows[0],["暂无可发布公司","未核验","未核验","未核验","未核验","未核验","未核验","未核验","未核验",self.pools.get("formal_top5",{}).get("reason"),"未评分"])
            for node in rows[1:]:node.set("style","display:none")
        riskmod=doc.get_element_by_id("stockRisk");riskcards=descendants_by_class(riskmod,"stock-risk-card")
        riskdata=[{"risk":x,"summary":"未核验 · 禁止升级核心池"} for x in self.risk.get("missing_fields",[])]+self.risk.get("items",[])
        def riskcard(node,item,index):
            bs=node.xpath(".//b");sp=node.xpath(".//span")
            if bs:set_node(bs[0],item.get("risk"))
            if sp:set_node(sp[0],item.get("summary") or item.get("level"))
        fill_existing(riskcards,riskdata,riskcard)
        funnel=doc.get_element_by_id("stockFunnel");levels=descendants_by_class(funnel,"funnel-level")
        for node,pair in zip(levels,[(len(candidate),"候选池｜行业相关＋基础数据"),(len(watch),"重点池｜产业链＋财务＋技术"),(len(core),"核心池｜全部风险门槛")]):
            bs=node.xpath(".//b");sp=node.xpath(".//span")
            if bs:set_node(bs[0],f"{pair[0]}只")
            if sp:set_node(sp[0],pair[1])
        pools=doc.get_element_by_id("stockPools");buttons=descendants_by_class(pools,"pool-tab")
        for node,pair in zip(buttons,[("候选池",len(candidate)),("重点池",len(watch)),("核心池",len(core))]):set_node(node,f"{pair[0]} {pair[1]}")
        candidate_rows=doc.get_element_by_id("candidate").xpath(".//tbody/tr")
        grouped=[]
        for sector in mapping:
            names=[x.get("name") or x.get("company") for x in candidate if x.get("sector")==sector.get("sector")]
            grouped.append({"sector":sector.get("sector"),"names":"、".join([x for x in names if x]) or "未达到公司级门槛","basis":sector.get("role"),"gate":"财务、技术与风险验证"})
        fill_existing(candidate_rows,grouped,lambda n,i,k:set_cells(n,[i.get("sector"),i.get("names"),i.get("basis"),i.get("gate")]))
        for node in candidate_rows[len(grouped):]:node.set("style","display:none")
        watch_rows=doc.get_element_by_id("watch").xpath(".//tbody/tr")
        if watch:
            fill_existing(watch_rows,watch,lambda n,i,k:set_cells(n,[i.get("name") or i.get("company"),i.get("sector"),i.get("pool_reason") or i.get("reason"),i.get("risk_summary")]))
            for node in watch_rows[len(watch):]:node.set("style","display:none")
        elif watch_rows:
            set_cells(watch_rows[0],["暂无重点池公司","未核验","公司数据或风险门槛未完成","不越级发布"])
            for node in watch_rows[1:]:node.set("style","display:none")
        top=doc.get_element_by_id("stockTop");notice=first_by_class(top,"notice")
        if notice is not None:
            published=self.pools.get("formal_top5",{}).get("published")
            bs=notice.xpath("./b")
            notice.text=None
            if bs:
                set_node(bs[0],"正式TOP 5已发布。" if published else "暂不发布正式TOP 5。")
                bs[0].tail=" "+text(self.pools.get("formal_top5",{}).get("reason"))
        states=descendants_by_class(top,"data-state");state_data=[("行业涨跌与成交","参与判断"),("最新季度财务","完整后参与筛选"),("5/20/60日与均线","完整后参与结构"),("减持/解禁/监管","不足则关闭TOP5"),("ETF申赎","缺失需标注"),("融资融券","缺失需标注"),("产业链主营","需业务占比"),("估值与预期差","待补充")]
        for node,pair in zip(states,state_data):
            bs=node.xpath(".//b");sp=node.xpath(".//span")
            if bs:set_node(bs[0],pair[0])
            if sp:set_node(sp[0],pair[1])

    def set_page(self,doc,default_page):
        for tab in descendants_by_class(doc,"tab"):
            tab.set("class","tab active" if tab.get("data-page")==default_page else "tab")
        for page in descendants_by_class(doc,"page"):
            page.set("class","page active" if page.get("id")==default_page else "page")

    def render(self,default_page):
        doc=self.parse();self.scrub(doc);self.global_header(doc);self.overview(doc);self.decision(doc);self.comparison(doc);self.forecast_module(doc);self.macro_signals(doc);self.breadth_industries(doc);self.capital_lifecycle(doc);self.causes(doc);self.daily_events_evidence(doc);self.prediction_page(doc);self.stocks(doc);self.set_page(doc,default_page)
        return "<!DOCTYPE html>\n"+html.tostring(doc,encoding="unicode",method="html")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--bundle",required=True);parser.add_argument("--output",required=True);args=parser.parse_args()
    renderer=GoldenRenderer(Path(__file__).resolve().parents[1],read_json(args.bundle));output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    for filename,page in {"market-intelligence-console.html":"market","market-map.html":"market","market-forecast.html":"prediction","stock-selection-center.html":"stocks"}.items():
        target=output/filename;target.write_text(renderer.render(page),encoding="utf-8");print(target)


if __name__=="__main__":main()
