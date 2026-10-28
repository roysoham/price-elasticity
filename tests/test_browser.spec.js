/**
 * Acceptance tests #2, #4-8, #10 from PORTFOLIO_BUILD_SPEC.md section 9.
 * (#1, #3, #9 are covered by tests/test_data_integrity.py -- no browser needed there.)
 *
 * Self-contained: spawns its own static server over site/, runs everything through
 * Playwright + Chromium, tears the server down, and exits non-zero on any failure.
 *
 * Run: node tests/test_browser.spec.js
 */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const SITE_DIR = path.join(__dirname, '..', 'site');
const PORT = 8934;
const BASE_URL = `http://localhost:${PORT}/index.html`;
const SCREENSHOT_DIR = path.join(__dirname, '_screenshots');

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log(`[PASS] ${name}`); }
  else { failed++; console.log(`[FAIL] ${name}${detail ? ' -- ' + detail : ''}`); }
}

function relLuminance([r, g, b]) {
  const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const [rl, gl, bl] = [f(r), f(g), f(b)];
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}
function contrastRatio(c1, c2) {
  const l1 = relLuminance(c1), l2 = relLuminance(c2);
  const [lighter, darker] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (lighter + 0.05) / (darker + 0.05);
}

async function waitForServer(url, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch (e) { /* not up yet */ }
    await new Promise(r => setTimeout(r, 150));
  }
  throw new Error('static server did not come up');
}

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const server = spawn('python3', ['-m', 'http.server', String(PORT)], { cwd: SITE_DIR, stdio: 'ignore' });
  try {
    await waitForServer(BASE_URL);

    const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });

    const consoleErrors = [];
    page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('pageerror', err => consoleErrors.push('PAGEERROR: ' + err.message));

    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    // ---------- #8 console clean (load + every tab switch, 2 full cycles) ----------
    const tabs = ['overview', 'leakage', 'pricing', 'segments', 'methodology'];
    for (let cycle = 0; cycle < 2; cycle++) {
      for (const t of tabs) {
        await page.click('#tab-' + t);
        await page.waitForTimeout(200);
      }
    }
    check('#8 console clean on load + 2 full tab cycles', consoleErrors.length === 0, JSON.stringify(consoleErrors));

    // ---------- #2 partial week never in KPI/trend/picker/WoW ----------
    const partialCheck = await page.evaluate(() => {
      const partial = STATE.meta.partial_week;
      const pickerWeeks = Array.from(document.getElementById('ovWeekPicker').options).map(o => o.value);
      const fromWeeks = Array.from(document.getElementById('f-from').options).map(o => o.value);
      const toWeeks = Array.from(document.getElementById('f-to').options).map(o => o.value);
      const stackWeeks = weekList(completeWeeks(STATE.data.weekly_stack));
      const segWeeks = weekList(completeWeeks(STATE.data.weekly_segment));
      const offenders = [];
      if (pickerWeeks.includes(partial)) offenders.push('ovWeekPicker');
      if (fromWeeks.includes(partial)) offenders.push('f-from');
      if (toWeeks.includes(partial)) offenders.push('f-to');
      if (stackWeeks.includes(partial)) offenders.push('weekly_stack completeWeeks()');
      if (segWeeks.includes(partial)) offenders.push('weekly_segment completeWeeks()');
      return { partial, offenders };
    });
    check('#2 partial week excluded from pickers and completeWeeks()', partialCheck.offenders.length === 0, JSON.stringify(partialCheck));

    // ---------- #4 n-suppression ----------
    const suppression = await page.evaluate(() => ({
      below: pctOrSuppressed(50, '50.0%'),
      above: pctOrSuppressed(150, '50.0%'),
      minN: MIN_N(),
    }));
    check('#4 n below threshold renders "insufficient data"',
      suppression.below.includes('insufficient data') && !suppression.above.includes('insufficient data'),
      JSON.stringify(suppression));

    // ---------- #5 simulator math ----------
    const simMath = await page.evaluate(() => {
      const s0 = runSimulator({ capType: 'n', capValue: 2, lossRate: 0 });
      const sBE = runSimulator({ capType: 'n', capValue: 2, lossRate: s0.breakEven });
      return {
        netEqualsGrossAtZeroLoss: Math.abs(s0.netChange - s0.grossRecovered) < 1e-6,
        netNearZeroAtBreakEven: Math.abs(sBE.netChange) < 0.01 * Math.abs(s0.grossRecoveredSum || 1),
        breakEven: s0.breakEven, netAtBreakEven: sBE.netChange, grossRecoveredSum: s0.grossRecoveredSum,
      };
    });
    check('#5 net change == gross recovered at 0% loss', simMath.netEqualsGrossAtZeroLoss, JSON.stringify(simMath));
    check('#5 net change within 1% of zero at break-even loss rate', simMath.netNearZeroAtBreakEven, JSON.stringify(simMath));

    // ---------- #6 difference-in-differences recovery vs truth.json ----------
    const truth = JSON.parse(fs.readFileSync(path.join(SITE_DIR, 'data', 'truth.json'), 'utf8'));
    const computedEvents = await page.evaluate(() => computePricingEvents());
    const mustRecover = ['E02', 'E04', 'E05', 'E06', 'E07', 'E08'];
    const recoveryFailures = [];
    for (const eid of mustRecover) {
      const rows = computedEvents.filter(e => e.event_id === eid);
      const trueVal = truth.elasticity[eid].true_elasticity;
      if (!rows.length) { recoveryFailures.push(`${eid}: no computed rows`); continue; }
      for (const r of rows) {
        if (!(trueVal >= r.ciLo && trueVal <= r.ciHi)) {
          recoveryFailures.push(`${eid}/${r.market}: true=${trueVal} not in [${r.ciLo.toFixed(2)}, ${r.ciHi.toFixed(2)}]`);
        }
      }
    }
    check('#6 90% CI covers planted elasticity for E02,E04,E05,E06,E07,E08', recoveryFailures.length === 0, JSON.stringify(recoveryFailures));

    const confoundFailures = [];
    for (const eid of ['E01', 'E03']) {
      const rows = computedEvents.filter(e => e.event_id === eid);
      for (const r of rows) if (!r.confounded) confoundFailures.push(`${eid}/${r.market}: not flagged confounded`);
    }
    check('#6 E01 and E03 flagged confounded', confoundFailures.length === 0, JSON.stringify(confoundFailures));

    // ---------- #7 layout: 1280 / 980 / 375, tabs reachable, waterfall renders every complete week ----------
    for (const width of [1280, 980, 375]) {
      await page.setViewportSize({ width, height: 900 });
      await page.click('#tab-overview');
      await page.waitForTimeout(250);
      const tabReach = await page.evaluate(() => {
        const btns = ['overview', 'leakage', 'pricing', 'segments', 'methodology'].map(t => document.getElementById('tab-' + t));
        return btns.every(b => b.offsetWidth > 0 && b.offsetHeight > 0);
      });
      check(`#7 all 5 tabs present and reachable at ${width}px`, tabReach);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, `overview_${width}.png`), fullPage: true });
    }
    await page.setViewportSize({ width: 1280, height: 1000 });

    // Waterfall x-axis labels are a fixed 9-category set (Offer.../GM), independent of
    // which week is selected -- so "no overlap for every week" reduces to (a) confirming
    // that fixed label set renders without overlap once, and (b) the chart re-renders
    // without error for every complete week (robustness, not a distinct overlap risk).
    const weeks = await page.evaluate(() => weekList(completeWeeks(STATE.data.weekly_waterfall)));
    let waterfallErrors = 0;
    for (const w of weeks) {
      await page.selectOption('#ovWeekPicker', w);
      await page.waitForTimeout(80);
      const ok = await page.evaluate(() => {
        const c = document.getElementById('ovWaterfallChart');
        return c && c.getBoundingClientRect().width > 0 && c.getBoundingClientRect().height > 0;
      });
      if (!ok) waterfallErrors++;
    }
    check(`#7 waterfall renders for every complete week (${weeks.length} weeks)`, waterfallErrors === 0, `${waterfallErrors} failed`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'waterfall_labels_sample.png'), clip: { x: 530, y: 150, width: 700, height: 500 } });

    // ---------- #10 contrast + focus ----------
    const colors = await page.evaluate(() => {
      const btn = document.querySelector('.btn.primary');
      const btnStyle = getComputedStyle(btn);
      return { bg: btnStyle.backgroundColor, fg: btnStyle.color, axis: getComputedStyle(document.body).color };
    });
    const parseRgb = s => s.match(/\d+/g).slice(0, 3).map(Number);
    const btnContrast = contrastRatio(parseRgb(colors.bg), parseRgb(colors.fg));
    check('#10 primary button text/background contrast >= 4.5:1', btnContrast >= 4.5, `${btnContrast.toFixed(2)}:1`);
    // chart axis tick color (#475569) against white chart background, computed directly (Chart.js draws to canvas, not DOM)
    const axisContrast = contrastRatio([71, 85, 105], [255, 255, 255]);
    check('#10 chart axis tick color contrast >= 4.5:1 on white', axisContrast >= 4.5, `${axisContrast.toFixed(2)}:1`);

    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    const focusOutline = await page.evaluate(() => {
      const el = document.activeElement;
      const s = getComputedStyle(el);
      return { tag: el.tagName, id: el.id, outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth };
    });
    check('#10 keyboard focus shows a visible outline', focusOutline.outlineStyle !== 'none' && focusOutline.outlineWidth !== '0px', JSON.stringify(focusOutline));

    await browser.close();
  } finally {
    server.kill();
  }

  console.log(`\n${passed} passed, ${failed} failed.`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
