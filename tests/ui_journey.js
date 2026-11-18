// Phone journey through the NEURON web page: pair, give a goal with a file, watch it finish, download.
const { chromium } = require('playwright');
const [base, code, csv, shots] = process.argv.slice(2);
const https = base.startsWith('https');
const out = { steps: [], problems: [] };
const note = (s) => out.steps.push(s);
const problem = (s) => out.problems.push(s);

async function audit(page, name) {
  const r = await page.evaluate(() => {
    const text = document.body.innerText;
    const bordered = [...document.querySelectorAll('.card, .item, .btn, textarea, input, .stat, .out a')].filter(el => {
      const cs = getComputedStyle(el);
      return ['Top', 'Right', 'Bottom', 'Left'].some(s => parseFloat(cs['border' + s + 'Width']) > 0 && cs['border' + s + 'Style'] !== 'none'
        && !cs['border' + s + 'Color'].includes('rgba(0, 0, 0, 0)'));
    }).map(el => el.className || el.tagName);
    return { emdash: text.includes('—'), overflow: document.documentElement.scrollWidth > window.innerWidth + 1, bordered,
      bg: getComputedStyle(document.body).backgroundColor };
  });
  if (r.emdash) problem(`${name}: em dash on screen`);
  if (r.overflow) problem(`${name}: page scrolls sideways on a phone`);
  if (r.bordered.length) problem(`${name}: border lines on ${r.bordered.slice(0, 3).join(', ')}`);
  const [cr, cg, cb] = r.bg.match(/\d+/g).map(Number);
  if (cr + cg + cb < 600) problem(`${name}: background is not light (${r.bg})`);
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}

(async () => {
  const browser = await chromium.launch();
  // over HTTPS the test accepts NEURON's own certificate, as the owner does after checking its fingerprint
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
    ignoreHTTPSErrors: https });
  try {
    await page.goto(base + '/');
    await page.waitForSelector('#code');
    note('opened: asked to pair');
    await audit(page, '1-pair');
    await page.fill('#code', '999999' === code ? '111111' : '999999');
    await page.click('#pair');
    await page.waitForSelector('.err');
    note('wrong code refused: ' + (await page.textContent('.err')));
    await page.fill('#code', code);
    await page.click('#pair');
    await page.waitForSelector('#goal');
    note('paired: home screen');
    await audit(page, '2-home');
    await page.fill('#goal', 'Make expenses.xlsx: rows on a sheet Data; a sheet Summary with the total per category and a Total row, using formulas.');
    await page.setInputFiles('#pick', csv);
    await page.waitForSelector('.chip');
    await page.click('#go');
    await page.waitForURL(/#\/job\//);
    note('job started');
    await page.waitForFunction(() => /Done and checked|Not done|Partly done/.test(document.querySelector('.badge')?.textContent || ''), null, { timeout: 180000 });
    const badge = await page.textContent('.badge');
    note('job finished: ' + badge);
    if (badge !== 'Done and checked') problem('job did not finish as checked: ' + badge);
    await audit(page, '3-job');
    const link = await page.$('.out a[href*="expenses.xlsx"]');
    if (!link) problem('no download link for expenses.xlsx');
    else {
      const [dl] = await Promise.all([page.waitForEvent('download').catch(() => null), link.click()]);
      const ok = dl ? (await dl.failure()) === null : false;
      note('download ' + (ok ? 'worked' : 'failed'));
      if (!ok) problem('download failed');
    }
    await page.fill('#more', 'Also add the number of expenses per category.');
    await page.click('#send');
    await page.waitForSelector('.thread .said');
    note('follow-up sent: earlier request shown in the conversation');
    await page.waitForFunction(() => /Done and checked|Not done|Partly done/.test(document.querySelector('.card:not(.thread) .badge')?.textContent || ''), null, { timeout: 180000 });
    note('follow-up finished: ' + (await page.textContent('.card:not(.thread) .badge')));
    await audit(page, '3b-follow-up');
    await page.click('.thread .said');
    await page.waitForSelector('#more');
    const checks = await page.$$eval('.ck b.ok', els => els.length);
    note(`evidence checks shown as passed: ${checks}`);
    if (!checks) problem('no evidence shown');
    await page.goto(base + '/#/status');
    await page.waitForSelector('.stat');
    note('status: ' + (await page.$$eval('.stat', els => els.map(e => e.innerText.replace(/\n/g, ' ')).join(' | '))));
    await audit(page, '4-status');
    await page.goto(base + '/#/');
    await page.waitForSelector('.item');
    note('recent work listed: ' + (await page.textContent('.item .t')));
  } catch (e) {
    let shown = '';
    try { shown = (await page.evaluate(() => location.hash + ' | ' + document.body.innerText.replace(/\s+/g, ' '))).slice(0, 300); } catch (x) { }
    problem('journey broke: ' + e.message.split('\n')[0] + ' | page: ' + shown);
  }
  await browser.close();
  console.log(JSON.stringify(out));
})();
