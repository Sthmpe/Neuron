// Dev checker for computed totals (catering orders; not a locked task). Uses the app like a person; never reads its code.
//   node repair_app.js <base url> <phase 1|2> <out dir>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const [base, phase, outDir] = process.argv.slice(2);
const LOGIN = { username: 'chef', password: 'jollof7' };
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
    await attempt('login_works', async () => { await login(p); await p.goto(base + '/'); return !(await hasPw(p)); });
    await attempt('add_dishes', async () => { for (const r of [{ Name: 'Jollof rice', Price: '2500' }, { Name: 'Moi moi', Price: '800' }]) { await open(p, 'Dishes'); await fill(p, r); }
      await open(p, 'Dishes'); const t = await text(p); return t.includes('Jollof rice') && t.includes('Moi moi'); });
    await attempt('add_orders', async () => {
      await open(p, 'Orders'); await fill(p, { Dish: 'Jollof', 'Plates|Number': '40', Customer: 'Ada Eze', 'Date|Event': '2027-01-15' });
      await open(p, 'Orders'); await fill(p, { Dish: 'Moi', 'Plates|Number': '25', Customer: 'Bayo Ade', 'Date|Event': '2027-02-20' });
      await open(p, 'Orders'); const t = await text(p); return { pass: t.includes('Ada Eze') && t.includes('Bayo Ade'), detail: t.slice(0, 200) }; });
    await attempt('order_totals_shown', async () => { await open(p, 'Orders'); const t = (await text(p)).replace(/,/g, '').replace(/\.0+\b/g, '');
      return { pass: /\b100000\b/.test(t) && /\b20000\b/.test(t), detail: 'needs 100000 and 20000' }; });
    await attempt('dashboard_count_and_total', async () => { await p.goto(base + '/'); const t = await text(p);
      return { pass: near(t, 'orders', '2') && near(t, '(total|value)', '120000'), detail: t.slice(0, 300) }; });
    await attempt('search_by_customer', async () => { await open(p, 'Orders'); const s = p.locator('input[type=search], input[name=q], input[name*=search i]').first();
      await s.fill('Bayo'); await s.press('Enter'); await p.waitForLoadState(); const t = await text(p); return t.includes('Bayo Ade') && !t.includes('Ada Eze'); });
  } catch (e) { check('checker_finished', false, e.message); }
  check('no_server_errors', errors.length === 0, errors.slice(0, 3).join('; '));
  await b.close(); console.log(JSON.stringify({ checks }));
})();
