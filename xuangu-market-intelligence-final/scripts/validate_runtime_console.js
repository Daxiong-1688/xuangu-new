#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const reports = path.resolve(process.argv[2]);
const bundlePath = path.resolve(process.argv[3]);
const bundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8'));
const files = {
  'market-intelligence-console.html': 'market',
  'market-map.html': 'market',
  'market-forecast.html': 'prediction',
  'stock-selection-center.html': 'stocks',
};
const stale = ['华丰科技','百奥赛图','万辰集团','铖昌科技','智明达','世纪华通','通化东宝','中顺洁柔','海兰信','光线传媒','蓝色光标'];
const currentStocks = new Set(['candidate','watch','core'].flatMap(pool => bundle.stock_pools?.[pool] || []).map(x => x.name || x.company).filter(Boolean));
const staleForbidden = stale.filter(name => !currentStocks.has(name));
const expectedCore = (bundle.stock_pools?.core || []).length;
const tradeDate = String(bundle.metadata?.resolved_trading_date || '');
const risk = String(bundle.market_map?.risk_score ?? '');
const chrome = process.env.XUANGU_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async () => {
  const options = {headless: true};
  if (fs.existsSync(chrome)) options.executablePath = chrome;
  const browser = await chromium.launch(options);
  const results = [];
  const errors = [];
  for (const [file, expected] of Object.entries(files)) {
    const source = path.join(reports, file);
    if (!fs.existsSync(source)) { errors.push(`缺少页面：${file}`); continue; }
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const browserErrors = [];
    page.on('pageerror', error => browserErrors.push(String(error)));
    page.on('console', message => { if (message.type() === 'error') browserErrors.push(message.text()); });
    await page.goto('file://' + source, {waitUntil: 'load'});
    await page.waitForTimeout(350);
    const state = await page.evaluate(({staleForbidden, tradeDate, risk}) => ({
      active: [...document.querySelectorAll('.page.active')].map(node => node.id),
      industries: document.querySelectorAll('#industries tbody tr').length,
      forecastMounted: Boolean(document.querySelector('#forecastMount #forecast')),
      coreRows: document.querySelectorAll('#coreRows tr').length,
      stale: staleForbidden.filter(name => document.body.innerText.includes(name)),
      date: document.body.innerText.includes(tradeDate),
      risk: document.body.innerText.includes(`风险 ${risk}/100`) || document.body.innerText.includes(`风险指数 ${risk}/100`),
    }), {staleForbidden, tradeDate, risk});
    const pageErrors = [];
    if (browserErrors.length) pageErrors.push(`浏览器错误：${browserErrors.join(' | ')}`);
    if (state.active.length !== 1 || state.active[0] !== expected) pageErrors.push(`活动页面错误：${JSON.stringify(state.active)}`);
    if (state.industries !== 31) pageErrors.push(`行业卡片${state.industries} != 31`);
    if (!state.forecastMounted) pageErrors.push('预测模块未进入forecastMount');
    if (state.coreRows !== expectedCore) pageErrors.push(`核心池行数${state.coreRows} != ${expectedCore}`);
    if (state.stale.length) pageErrors.push(`残留黄金样本：${state.stale.join('、')}`);
    if (!state.date) pageErrors.push(`未显示交易日${tradeDate}`);
    if (!state.risk) pageErrors.push(`未显示风险指数${risk}`);
    if (pageErrors.length) errors.push(`${file}：${pageErrors.join('；')}`);
    results.push({file, expected, ...state, browserErrors});
    await page.close();
  }
  await browser.close();
  const report = {valid: errors.length === 0, generated_at: new Date().toISOString(), results, errors};
  fs.writeFileSync(path.join(reports, 'runtime-validation.json'), JSON.stringify(report, null, 2));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('RUNTIME CONSOLE VALID · 4 pages · 31 industries · no stale samples · no browser errors');
})().catch(error => { console.error(error.message || error); process.exit(1); });
