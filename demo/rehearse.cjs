'use strict';
const { chromium } = require('playwright');
const path = require('path');

const FILE_URL = 'file:///' + path.resolve(__dirname, '../frontend/index.html').replace(/\\/g, '/');

async function ensureVisible(page, selector, label) {
  const el = page.locator(selector).first();
  const visible = await el.isVisible().catch(() => false);
  if (!visible) {
    const found = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button,input,select,[id]'))
        .filter(e => e.offsetParent !== null && e.id)
        .map(e => `#${e.id}`).join(', ')
    );
    console.error(`FAIL: "${label}" — selector: ${selector}`);
    console.error(`  IDs on page: ${found.substring(0, 200)}`);
    return false;
  }
  console.log(`  OK: ${label}`);
  return true;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto(FILE_URL);
  await page.waitForTimeout(5000); // let simulator warm up

  console.log('\n── Rehearsing selectors ──');
  const checks = [
    ['#conn-label',               'Connection status label'],
    ['#kpi-faults-val',           'KPI — arms in fault'],
    ['#kpi-anom-val',             'KPI — anomalies/hr'],
    ['#kpi-z-val',                'KPI — worst Z-score'],
    ['#card-arm_01',              'Arm 01 card'],
    ['#card-arm_02',              'Arm 02 card'],
    ['#card-arm_03',              'Arm 03 card'],
    ['#badge-arm_01',             'Arm 01 fault badge'],
    ['#badge-arm_02',             'Arm 02 fault badge'],
    ['#m-arm_02-temperature',     'Arm 02 temperature metric tile'],
    ['#m-arm_02-vibration',       'Arm 02 vibration metric tile'],
    ['canvas#chart-temp',         'Temperature chart canvas'],
    ['canvas#chart-z',            'Z-score chart canvas'],
    ['button[data-min="30"]',     'Time window — 30m button'],
    ['button[data-min="60"]',     '  Time window — 1h button'],
    ['button[data-filter="faults"]', 'Log filter — Faults Only'],
    ['button[data-filter="arm_02"]', 'Log filter — Arm 02'],
    ['#log-body',                 'Anomaly log table body'],
    ['#last-update',              'Last update footer label'],
  ];

  let allOk = true;
  for (const [sel, label] of checks) {
    if (!await ensureVisible(page, sel, label)) allOk = false;
  }

  console.log('\n── Verifying modal flow ──');
  await page.locator('#m-arm_02-temperature').first().click();
  await page.waitForTimeout(600);
  const modalOpen = await page.locator('.modal-overlay.open').isVisible().catch(() => false);
  console.log(modalOpen ? '  OK: modal opens on metric click' : 'FAIL: modal did not open');
  if (modalOpen) {
    const closeBtn = await page.locator('.m-close').isVisible().catch(() => false);
    console.log(closeBtn ? '  OK: modal close button visible' : 'FAIL: modal close button missing');
    await page.locator('.m-close').click();
    await page.waitForTimeout(400);
  }

  console.log('\n── Verifying fault injection ──');
  await page.evaluate(() => {
    if (typeof sim !== 'undefined') {
      sim.faults['arm_02'] = { mode: 'THERMAL_DRIFT', until: Date.now() + 20000 };
    }
  });
  await page.waitForTimeout(3000);
  const badgeText = await page.locator('#badge-arm_02').textContent().catch(() => '');
  const faultVisible = badgeText.includes('THERMAL');
  console.log(faultVisible
    ? `  OK: fault injection works — badge shows "${badgeText.trim()}"`
    : `FAIL: fault injection — badge shows "${badgeText.trim()}" (expected THERMAL DRIFT)`);
  if (!faultVisible) allOk = false;

  const fdur = await page.locator('#fdur-arm_02').textContent().catch(() => '');
  console.log(fdur ? `  OK: fault duration visible — "${fdur.trim()}"` : 'FAIL: fault duration not showing');

  await browser.close();
  if (allOk) {
    console.log('\n✓ REHEARSAL PASSED — all selectors verified\n');
    process.exit(0);
  } else {
    console.error('\n✗ REHEARSAL FAILED — fix selectors before recording\n');
    process.exit(1);
  }
})();
