'use strict';
const { chromium } = require('playwright');
const path = require('path');
const fs   = require('fs');

const FILE_URL  = 'file:///' + path.resolve(__dirname, '../frontend/index.html').replace(/\\/g, '/');
const VIDEO_DIR = path.join(__dirname, 'output');
const OUT_FILE  = path.join(VIDEO_DIR, 'iiot-smart-factory-demo.webm');

if (!fs.existsSync(VIDEO_DIR)) fs.mkdirSync(VIDEO_DIR, { recursive: true });

/* ── helpers ── */
async function injectOverlays(page) {
  await page.evaluate(() => {
    // cursor
    if (!document.getElementById('demo-cursor')) {
      const c = document.createElement('div');
      c.id = 'demo-cursor';
      c.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/>
      </svg>`;
      c.style.cssText = 'position:fixed;z-index:999999;pointer-events:none;width:22px;height:22px;' +
        'transition:left 0.08s,top 0.08s;filter:drop-shadow(1px 1px 2px rgba(0,0,0,.4))';
      c.style.left = '640px'; c.style.top = '360px';
      document.body.appendChild(c);
      document.addEventListener('mousemove', e => {
        c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
      });
    }
    // subtitle
    if (!document.getElementById('demo-sub')) {
      const s = document.createElement('div');
      s.id = 'demo-sub';
      s.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:999998;text-align:center;' +
        'padding:11px 24px;background:rgba(0,0,0,.72);color:#fff;' +
        'font-family:-apple-system,"Segoe UI",sans-serif;font-size:15px;font-weight:500;' +
        'letter-spacing:.3px;transition:opacity .3s;pointer-events:none;opacity:0';
      document.body.appendChild(s);
    }
  });
}

async function sub(page, text, wait = 900) {
  await page.evaluate(t => {
    const s = document.getElementById('demo-sub');
    if (!s) return;
    s.textContent = t; s.style.opacity = t ? '1' : '0';
  }, text);
  if (text && wait) await page.waitForTimeout(wait);
}

async function move(page, selector, opts = {}) {
  const { delay = 400, postDelay = 700 } = opts;
  const el = page.locator(selector).first();
  const box = await el.boundingBox().catch(() => null);
  if (!box) { console.warn('move: no box for', selector); return; }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await page.waitForTimeout(delay);
  await el.click();
  await page.waitForTimeout(postDelay);
}

async function hover(page, selector, wait = 700) {
  const el = page.locator(selector).first();
  const box = await el.boundingBox().catch(() => null);
  if (!box) return;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await page.waitForTimeout(wait);
}

async function pan(page, selectors) {
  for (const sel of selectors) await hover(page, sel, 800);
}

/* ── record ── */
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 720 } },
    viewport:    { width: 1280, height: 720 },
  });
  const page = await context.newPage();

  try {
    // ── [0:00] Load + warm-up ─────────────────────────────────────────
    await page.goto(FILE_URL);
    await injectOverlays(page);
    await sub(page, 'Unplanned downtime in automotive manufacturing costs €500k+ per hour', 0);
    await page.waitForTimeout(5000); // simulator warm-up + initial data

    // ── [0:05] Connection confirmed ───────────────────────────────────
    await sub(page, 'iiot-smart-factory-sim — 3 robotic arms · 9 sensor channels · live telemetry');
    await page.waitForTimeout(2500);

    // ── [0:08] Pan KPI bar ────────────────────────────────────────────
    await sub(page, 'Fleet health at a glance — faults, anomaly rate, worst Z-score');
    await pan(page, ['#kpi-faults', '#kpi-anom', '#kpi-z']);
    await page.waitForTimeout(1000);

    // ── [0:14] Pan arm cards ──────────────────────────────────────────
    await sub(page, 'All three arms nominal — temperature, vibration, and motor current streaming');
    await pan(page, ['#card-arm_01', '#card-arm_02', '#card-arm_03']);
    await page.waitForTimeout(1500);

    // ── [0:21] Open metric modal ──────────────────────────────────────
    await sub(page, 'Click any sensor tile for live statistics and Z-score analysis');
    await move(page, '#m-arm_02-temperature', { postDelay: 1200 });
    await page.waitForTimeout(2500);

    // ── [0:26] Close modal ────────────────────────────────────────────
    await sub(page, '');
    await move(page, '.m-close', { postDelay: 800 });

    // ── [0:28] Scroll to charts ───────────────────────────────────────
    await sub(page, 'Time-series charts — one line per arm across the selected window');
    await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'smooth' }));
    await page.waitForTimeout(1800);
    await hover(page, 'canvas#chart-temp', 1200);

    // ── [0:33] Switch to 30m window ───────────────────────────────────
    await sub(page, '');
    await move(page, 'button[data-min="30"]', { postDelay: 800 });

    // ── [0:35] Z-score chart ──────────────────────────────────────────
    await page.evaluate(() => window.scrollTo({ top: 900, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await sub(page, 'Z-score chart — sliding window 30 samples · ±3.0σ anomaly threshold');
    await hover(page, 'canvas#chart-z', 2200);

    // ── [0:42] Inject THERMAL_DRIFT on arm_02 ────────────────────────
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1200);
    await sub(page, 'Watch Arm 02 — injecting a thermal drift fault now…');
    await page.evaluate(() => {
      if (typeof sim !== 'undefined')
        sim.faults['arm_02'] = { mode: 'THERMAL_DRIFT', until: Date.now() + 30000 };
    });
    await page.waitForTimeout(3000); // wait for next tick to pick it up

    // ── [0:47] Fault detected ─────────────────────────────────────────
    await sub(page, 'THERMAL DRIFT detected · badge, fault timer, and toast fire within one poll cycle');
    await hover(page, '#card-arm_02', 2000);
    await pan(page, ['#badge-arm_02', '#fdur-arm_02', '#kpi-faults']);
    await page.waitForTimeout(1000);

    // ── [0:52] Faults log ─────────────────────────────────────────────
    await page.evaluate(() => window.scrollTo({ top: 1400, behavior: 'smooth' }));
    await page.waitForTimeout(1200);
    await sub(page, 'Anomaly log — ACTIVE / RESOLVED status · one-click ACK · full audit trail');
    await move(page, 'button[data-filter="faults"]', { postDelay: 1200 });
    await page.waitForTimeout(1500);

    // ── [0:57] Closing title ──────────────────────────────────────────
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);
    await sub(page, 'docker compose up  —  entire stack in one command');
    await page.waitForTimeout(2500);
    await sub(page, 'Edge-deployable · Production-pattern · github.com/abhi-faldu/iiot-smart-factory-sim');
    await page.waitForTimeout(3000);
    await sub(page, '');
    await page.waitForTimeout(800);

  } catch (err) {
    console.error('DEMO ERROR:', err.message);
  } finally {
    await context.close();
    const vpath = await page.video()?.path().catch(() => null);
    if (vpath) {
      fs.copyFileSync(vpath, OUT_FILE);
      console.log('\nVideo saved to:', OUT_FILE);
    } else {
      console.error('No video path returned');
    }
    await browser.close();
  }
})();
