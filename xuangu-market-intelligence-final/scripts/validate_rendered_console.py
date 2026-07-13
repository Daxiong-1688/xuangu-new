#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from workflow_lib import read_json

GOLDEN_STOCKS={"华丰科技","百奥赛图","万辰集团","铖昌科技","智明达","世纪华通","通化东宝","中顺洁柔","海兰信","光线传媒","蓝色光标"}
GOLDEN_FORECAST_SENTINELS={"阿斯麦","台积电","WAIC","概率 55%","预测置信度64%","医药与军工进入重点池","07-13 → 07-19"}

def styles(text):
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>",text,flags=re.S))

def ids(text):
    return re.findall(r'id="([^"]+)"',text)

def skeleton(text):
    from lxml import html
    doc=html.document_fromstring(text)
    return [(node.tag,node.get("id")) for node in doc.xpath("//*")]

def is_hidden(node):
    return any("display:none" in (item.get("style") or "").replace(" ","").lower() for item in [node,*node.iterancestors()])

def sign_mismatch(node):
    value="".join(node.text_content().split())
    classes=(node.get("class") or "").split()
    return (value.startswith("-") and "positive" in classes) or (value.startswith("+") and "negative" in classes)

def main():
    p=argparse.ArgumentParser();p.add_argument("--html",required=True);p.add_argument("--bundle",required=True);args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    golden=(root/"assets/golden/market-intelligence-console.html").read_text(encoding="utf-8")
    rendered=Path(args.html).read_text(encoding="utf-8");bundle=read_json(args.bundle,{})
    errors=[]
    if hashlib.sha256(styles(golden).encode()).hexdigest()!=hashlib.sha256(styles(rendered).encode()).hexdigest():errors.append("CSS与最终黄金母版不一致")
    if skeleton(golden)!=skeleton(rendered):errors.append("模块内部DOM骨架与黄金母版不一致；禁止清空后重建模块")
    golden_ids=ids(golden);rendered_ids=ids(rendered)
    if [x for x in golden_ids if x not in {"coreRows","drawerContent","stockGrid"}]!=[x for x in rendered_ids if x not in {"coreRows","drawerContent","stockGrid"}]:errors.append("固定模块ID或顺序发生变化")
    if "const stocks=" not in rendered:errors.append("核心股票数据槽缺失")
    if re.search(r"(?:market|prediction|stocks)(?:Page)?\.innerHTML\s*=",rendered):errors.append("禁止使用运行时整页innerHTML覆盖黄金DOM")
    date_str=str(bundle.get("metadata",{}).get("resolved_trading_date") or "")
    if date_str and date_str not in rendered:errors.append("页面未显示本次交易日")
    scope={x.get("sector") for x in bundle.get("market_map",{}).get("dynamic_sector_scope",[]) if isinstance(x,dict)}
    for sector in scope:
        if sector and sector not in rendered:errors.append(f"动态板块未渲染：{sector}")
    current_stocks={x.get("name") for key in ("candidate","watch","core") for x in bundle.get("stock_pools",{}).get(key,[]) if isinstance(x,dict)}
    stale=sorted(name for name in GOLDEN_STOCKS-current_stocks if name in rendered)
    if stale:errors.append("页面残留黄金样本股票："+", ".join(stale))
    from lxml import html
    rendered_doc=html.document_fromstring(rendered)
    try:industry_count=len(rendered_doc.get_element_by_id("industries").xpath(".//tbody/tr"))
    except KeyError:industry_count=0
    if industry_count!=31:errors.append(f"行业全景源码不是31个行业行：{industry_count}")
    sign_errors=[]
    for row in rendered_doc.xpath('//*[@id="industries"]//tbody/tr'):
        name=row.xpath('./td')[0].text_content().strip() if row.xpath('./td') else "未知行业"
        for cell in row.xpath('./td')[1:4]:
            if sign_mismatch(cell):sign_errors.append(f"{name}:{cell.text_content().strip()}")
    for card in rendered_doc.xpath('//*[@id="causes"]//*[contains(concat(" ",normalize-space(@class)," ")," cause-pro ")]'):
        values=card.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," cause-return ")]')
        if values and sign_mismatch(values[0]):sign_errors.append(f"板块归因:{values[0].text_content().strip()}")
    if sign_errors:errors.append("涨跌颜色与数值符号冲突："+", ".join(sign_errors[:8]))
    confidence=bundle.get("forecast",{}).get("confidence")
    bars=rendered_doc.xpath('//*[@id="forecast"]//*[contains(concat(" ",normalize-space(@class)," ")," confidence-track ")]/i')
    if bars and isinstance(confidence,(int,float)) and f"width:{round(confidence*100)}%" not in (bars[0].get("style") or "").replace(" ",""):errors.append("预测置信度数字与进度条宽度不一致")
    for marker in rendered_doc.xpath('//*[@id="lifecycle"]//*[contains(concat(" ",normalize-space(@class)," ")," life-track ")]/i'):
        style=(marker.get("style") or "").replace(" ","")
        if "left:" not in style or "width:" in style:errors.append("热点生命周期标记仍含旧位置或错误宽度");break
    forecast=bundle.get("forecast",{})
    allowed={str(x.get("sector")) for x in forecast.get("sector_ranking",[]) if isinstance(x,dict)}|scope
    rank_rows=[x for x in rendered_doc.xpath('//*[@id="prediction"]//table[contains(concat(" ",normalize-space(@class)," ")," forecast-rank ")]//tbody/tr') if not is_hidden(x)]
    for row in rank_rows:
        cells=row.xpath('./td')
        sector=cells[1].text_content().strip() if len(cells)>1 else ""
        if sector and sector not in allowed:errors.append(f"预测排行残留非本次动态板块：{sector}")
    visible_text=" ".join(x.strip() for x in rendered_doc.get_element_by_id("prediction").xpath('.//text()') if x.strip() and not is_hidden(x.getparent()))
    evidence_blob=json.dumps(bundle,ensure_ascii=False)
    unsupported=sorted(x for x in GOLDEN_FORECAST_SENTINELS if x in visible_text and x not in evidence_blob)
    if unsupported:errors.append("未来预测页残留无Bundle证据的黄金样例："+", ".join(unsupported))
    raw_codes=[x for x in ("relative_bullish","relative_bearish","event_watch_only","oversold_watch_not_bottom") if x in visible_text]
    if raw_codes:errors.append("页面泄漏内部预测代码："+", ".join(raw_codes))
    try:
        trading=date.fromisoformat(date_str)
        start=trading+timedelta(days=1);end=trading+timedelta(days=7)
        expected=f"{start.year}年{start.month}月{start.day}日—{end.month}月{end.day}日"
        events_text=rendered_doc.get_element_by_id("events").text_content()
        if expected not in events_text:errors.append(f"未来7天标题日期范围错误，应为{expected}")
    except Exception:
        pass
    for day in rendered_doc.xpath('//*[@id="events"]//*[contains(concat(" ",normalize-space(@class)," ")," day-card ")]'):
        visible_events=[x for x in day.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," calendar-event ")]') if not is_hidden(x)]
        if not visible_events:errors.append("未来7天时间轴存在空白日期卡片");break
    if bundle.get("metadata",{}).get("analysis_mode")!="evidence_constrained_ai":
        pills=rendered_doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," pill ")]')
        if not pills or "草稿" not in pills[0].text_content():errors.append("非正式Bundle未在页面显著标记草稿状态")
    for button in rendered_doc.xpath('//*[@id="decision"]//button'):
        if "候选" in button.text_content() and "candidate" not in (button.get("onclick") or ""):errors.append("决策矩阵按钮文字与股票池目标不一致")
        if "暂不扩池" in button.text_content() and "openStockCenter" in (button.get("onclick") or ""):errors.append("暂不扩池按钮仍可跳转股票池")
    if errors:raise SystemExit("RENDER INVALID\n- "+"\n- ".join(errors))
    print("RENDERED CONSOLE VALID · GOLDEN UI + SEMANTICS PRESERVED")

if __name__=="__main__":main()
