'use strict';
const { chromium } = require('playwright');
const path = require('path');

const FILE_URL = 'file:///' + path.resolve(__dirname, '../frontend/index.html').replace(/\\/g, '/');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });

  console.log('Navigating to:', FILE_URL);
  await page.goto(FILE_URL);

  // Wait for simulator to kick in (API will be unreachable)
  await page.waitForTimeout(4000);

  console.log('\n=== PAGE TITLE ===');
  console.log(await page.title());

  console.log('\n=== CONNECTION STATUS ===');
  const connLabel = await page.locator('#conn-label').textContent().catch(() => 'N/A');
  console.log('Connection:', connLabel);

  console.log('\n=== INTERACTIVE ELEMENTS ===');
  const els = await page.evaluate(() => {
    const result = [];
    document.querySelectorAll('button, input, select, [onclick], .filter-pill, .tp, .metric').forEach(el => {
      if (el.offsetParent !== null) {
        result.push({
          tag: el.tagName,
          id: el.id || '',
          cls: el.className?.substring(0, 60) || '',
          text: el.textContent?.trim().substring(0, 50) || '',
          dataAttr: Object.fromEntries([...el.attributes].filter(a => a.name.startsWith('data-')).map(a => [a.name, a.value])),
        });
      }
    });
    return result;
  });
  els.forEach(e => console.log(JSON.stringify(e)));

  console.log('\n=== ARM CARD IDs ===');
  const cards = await page.locator('.arm-card').all();
  console.log('Arm cards found:', cards.length);
  for (const c of cards) console.log(' id:', await c.getAttribute('id'));

  console.log('\n=== METRIC TILES ===');
  const metrics = await page.locator('.metric').all();
  console.log('Metric tiles found:', metrics.length);
  for (const m of metrics) {
    const id = await m.getAttribute('id');
    const label = await m.locator('.label').textContent().catch(() => '');
    console.log(` id:${id}  label:${label}`);
  }

  console.log('\n=== CHART CANVASES ===');
  const canvases = await page.locator('canvas').all();
  for (const c of canvases) console.log(' id:', await c.getAttribute('id'));

  console.log('\n=== KPI BAR ===');
  const kpiBar = await page.locator('.kpi-bar').isVisible().catch(() => false);
  console.log('KPI bar visible:', kpiBar);
  if (kpiBar) {
    const faults = await page.locator('#kpi-faults-val').textContent().catch(() => 'N/A');
    const anom   = await page.locator('#kpi-anom-val').textContent().catch(() => 'N/A');
    const z      = await page.locator('#kpi-z-val').textContent().catch(() => 'N/A');
    console.log(`  Arms in Fault: ${faults}  Anomalies/hr: ${anom}  Worst Z: ${z}`);
  }

  console.log('\n=== LOG TABLE ===');
  const logVisible = await page.locator('#log-body').isVisible().catch(() => false);
  console.log('Log table visible:', logVisible);
  const logRows = await page.locator('#log-body tr').count();
  console.log('Log rows:', logRows);

  await browser.close();
})();
