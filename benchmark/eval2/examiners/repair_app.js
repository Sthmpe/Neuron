// Browser examiner for E10 (Tunde Fixes repair shop). Uses the app like a person; never reads its code.
//   node repair_app.js <base url> <phase 1|2> <out dir>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const [base, phase, outDir] = process.argv.slice(2);
const LOGIN = { username: 'tunde', password: 'spanner9' };
const checks = [], errors = [];
const rx = (s) => new RegExp(s, 'i');
const check = (id, pass, detail = '') => checks.push({ id, pass: !!pass, detail: String(detail).slice(0, 300) });
async function attempt(id, fn) { try { const r = await fn(); check(id, r === undefined ? true : (r.pass ?? r), r && r.detail); } catch (e) { check(id, false, e.message.split('\n')[0]); } }
const text = async (p) => (await p.locator('body').innerText()).replace(/ /g, ' ');
const hasPw = async (p) => (await p.locator('input[type=password]:visible').count()) > 0;
async function field(p, label) {
  for (const loc of [p.getByLabel(rx(label)), p.locator(`input[name*="${label}" i], select[name*="${label}" i], textarea[name*="${label}" i]`), p.getByPlaceholder(rx(label))]) {
    const n = await loc.count(); for (let i = 0; i < n; i++) if (await loc.nth(i).isVisible()) return loc.nth(i);
  }
  return null;
}
async function fill(p, record) {
  let last = null;
  for (const [labels, value] of Object.entries(record)) {
    let f = null;
    for (const label of labels.split('|')) { f = await field(p, label); if (f) break; }
    if (!f) { const add = p.getByRole('link', { name: /add|new|create/i }).first(); if (await add.count()) { await add.click(); await p.waitForLoadState();
      for (const label of labels.split('|')) { f = await field(p, label); if (f) break; } } }
    if (!f) throw new Error(`no field for ${labels}`);
    const tag = await f.evaluate(e => e.tagName);
    if (tag === 'SELECT') {
      const opts = await f.locator('option').allInnerTexts(); const pick = opts.find(o => o.toLowerCase().includes(String(value).toLowerCase()));
      if (!pick) throw new Error(`no option ${value} in ${labels}`); await f.selectOption({ label: pick });
    } else await f.fill(String(value));
    last = f;
  }
  const form = last.locator('xpath=ancestor::form[1]');
  const btn = form.locator('button[type=submit], input[type=submit], button:not([type])').first();
  if (await btn.count()) await btn.click(); else await last.press('Enter');
  await p.waitForLoadState();
}
async function login(p) {
  await p.goto(base + '/'); if (!(await hasPw(p))) { const l = p.getByRole('link', { name: /log ?in/i }).first(); if (await l.count()) { await l.click(); await p.waitForLoadState(); } }
  const u = (await field(p, 'user')) || (await field(p, 'name')); await u.fill(LOGIN.username);
  await p.locator('input[type=password]').first().fill(LOGIN.password); await p.locator('input[type=password]').first().press('Enter'); await p.waitForLoadState();
}
async function open(p, word) {
  await p.goto(base + '/');
  const a = p.getByRole('link', { name: rx(word) }).first();
  if (await a.count() && await a.isVisible()) await a.click();
  else { const t = p.locator('label.nav-toggle, button[aria-label*=menu i]').first(); if (await t.count() && await t.isVisible()) await t.click();
         if (await a.count() && await a.isVisible()) await a.click(); else await p.goto(base + '/' + word.toLowerCase()); }
  await p.waitForLoadState();
}
const near = (t, label, value) => new RegExp(`${label}[^0-9]{0,40}${value}(?![0-9])`, 'i').test(t.replace(/,/g, '').replace(/\.0+\b/g, '')) ||
  new RegExp(`(?<![0-9])${value}[^0-9]{0,30}${label}`, 'i').test(t.replace(/,/g, '').replace(/\.0+\b/g, ''));
(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } }); const p = await ctx.newPage();
  p.on('response', r => { if (r.status() >= 500) errors.push(`${r.status()} ${r.url().replace(base, '')}`); });
  try {
    if (phase === '1') {
      await attempt('login_required', async () => { await p.goto(base + '/'); if (await hasPw(p)) return true; await p.goto(base + '/repairs'); return { pass: await hasPw(p), detail: 'repairs opened without login' }; });
      await attempt('wrong_password_rejected', async () => { await p.goto(base + '/login'); const u = (await field(p, 'user')) || (await field(p, 'name')); await u.fill('tunde'); await p.locator('input[type=password]').first().fill('wrong'); await p.locator('input[type=password]').first().press('Enter'); await p.waitForLoadState(); await p.goto(base + '/repairs'); return await hasPw(p); });
      await attempt('login_works', async () => { await login(p); await p.goto(base + '/'); return !(await hasPw(p)); });
      await attempt('add_customers', async () => { for (const r of [{ Name: 'Kemi Bello', Phone: '0806 123 4567' }, { Name: 'Yusuf Garba', Phone: '0809 765 4321' }]) { await open(p, 'Customers'); await fill(p, r); }
        await open(p, 'Customers'); const t = await text(p); return t.includes('Kemi Bello') && t.includes('Yusuf Garba'); });
      await attempt('add_repairs', async () => {
        await open(p, 'Repairs'); await fill(p, { Customer: 'Kemi', Device: 'Tecno Spark screen', 'Parts': '12000', 'Labour|Labor': '8000' });
        await open(p, 'Repairs'); await fill(p, { Customer: 'Yusuf', Device: 'iPhone battery', 'Parts': '4000', 'Labour|Labor': '1500' });
        await open(p, 'Repairs'); const t = await text(p); return { pass: t.includes('Tecno Spark screen') && t.includes('iPhone battery'), detail: t.slice(0, 200) }; });
      await attempt('repairs_list_shows_totals', async () => { await open(p, 'Repairs'); const t = (await text(p)).replace(/,/g, '').replace(/\.0+\b/g, '');
        return { pass: /\b20000\b/.test(t) && /\b5500\b/.test(t), detail: 'needs 20000 and 5500' }; });
      await attempt('dashboard_numbers', async () => { await p.goto(base + '/'); const t = await text(p);
        return { pass: near(t, 'customers', '2') && near(t, 'repairs', '2') && near(t, '(billed|total)', '25500'), detail: t.slice(0, 300) }; });
      await attempt('works_on_a_phone', async () => { await p.setViewportSize({ width: 375, height: 740 }); const bad = [];
        for (const w of ['', 'Customers', 'Repairs']) { if (w) await open(p, w); else await p.goto(base + '/'); await p.screenshot({ path: `${outDir}/${w || 'dashboard'}-phone.png`, fullPage: true });
          if (await p.evaluate(() => document.documentElement.scrollWidth - innerWidth) > 2) bad.push(w || 'dashboard'); }
        await p.setViewportSize({ width: 1280, height: 800 }); return { pass: !bad.length, detail: bad.join(', ') }; });
      for (const w of ['', 'Customers', 'Repairs']) { if (w) await open(p, w); else await p.goto(base + '/'); await p.screenshot({ path: `${outDir}/${w || 'dashboard'}-desktop.png`, fullPage: true }); }
    } else {
      await attempt('data_survives_restart', async () => { await login(p); await open(p, 'Repairs'); const t = await text(p);
        await open(p, 'Customers'); const c = await text(p); return { pass: t.includes('Tecno Spark screen') && c.includes('Yusuf Garba') }; });
    }
  } catch (e) { check('examiner_finished', false, e.message); }
  check(phase === '1' ? 'no_server_errors' : 'no_server_errors_after_restart', errors.length === 0, errors.slice(0, 3).join('; '));
  await b.close(); console.log(JSON.stringify({ checks }));
})();
