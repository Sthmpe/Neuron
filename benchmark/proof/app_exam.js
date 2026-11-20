// Generic browser examiner for the core-proof app tasks. Uses the app like a person; never reads its code.
// Copied helpers from eval2's repair_app.js (eval2 itself is untouched).
//   node app_exam.js <base url> <phase 1|2> <out dir> <spec json file>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const [base, phase, outDir, specFile] = process.argv.slice(2);
const SPEC = JSON.parse(fs.readFileSync(specFile, 'utf8'));
const LOGIN = SPEC.login ? { username: SPEC.login[0], password: SPEC.login[1] } : null;
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
// Dashboard cards put the label on one line and the value on the next (a label may hold its own number, like
// "Fewer than 10 in stock"): accept that too, besides a value following the label on the same line.
const nearLines = (t, label, value) => {
  const L = t.replace(/,/g, '').replace(/\.0+\b/g, '').split('\n').map(x => x.trim()).filter(Boolean);
  const re = new RegExp(label, 'i'), v = new RegExp(`^${value}(?![0-9])`);
  return L.some((line, i) => re.test(line) && ((i + 1 < L.length && v.test(L[i + 1])) || (i > 0 && v.test(L[i - 1]))));
};
const nearAny = (t, label, value) => near(t, label, value) || nearLines(t, label, value);
async function step(p, s) {
  if (s.open) await open(p, s.open);
  if (s.fill) await fill(p, s.fill);
  if (s.fill && s.open && !s.stay) await open(p, s.open);   // stay: look at the page the form led to (a thank-you)
  if (s.search) { const box = p.locator('input[type=search], input[name=q], input[name*=search i]').first();
    await box.fill(s.search); await box.press('Enter'); await p.waitForLoadState(); }
  const raw = await text(p);
  const t = raw.replace(/,/g, '').replace(/\.0+\b/g, '');
  const missing = (s.expect || []).filter(x => !t.toLowerCase().includes(String(x).toLowerCase().replace(/,/g, '')));
  const present = (s.absent || []).filter(x => t.toLowerCase().includes(String(x).toLowerCase()));
  const far = (s.near || []).filter(([label, value]) => !nearAny(raw, label, value));
  return { pass: !missing.length && !present.length && !far.length,
           detail: (missing.length ? 'missing ' + missing.join(', ') + '; ' : '') + (present.length ? 'should not show ' + present.join(', ') + '; ' : '') +
                   (far.length ? 'not near: ' + far.map(f => f.join('=')).join(', ') : '') };
}
(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } }); const p = await ctx.newPage();
  p.on('response', r => { if (r.status() >= 500) errors.push(`${r.status()} ${r.url().replace(base, '')}`); });
  try {
    if (phase === '1') {
      if (LOGIN) {
        await attempt('login_required', async () => { await p.goto(base + '/'); if (await hasPw(p)) return true; const first = (SPEC.steps.find(s => s.open && s.open !== '/') || {}).open || '';
          await p.goto(base + '/' + first.toLowerCase()); return { pass: await hasPw(p), detail: 'a page opened without logging in' }; });
        await attempt('wrong_password_rejected', async () => { await p.goto(base + '/login'); const u = (await field(p, 'user')) || (await field(p, 'name')); await u.fill(LOGIN.username);
          await p.locator('input[type=password]').first().fill('wrong-pass'); await p.locator('input[type=password]').first().press('Enter'); await p.waitForLoadState();
          await p.goto(base + '/'); return await hasPw(p); });
        await attempt('login_works', async () => { await login(p); await p.goto(base + '/'); return !(await hasPw(p)); });
      }
      for (const s of SPEC.steps) await attempt(s.id, async () => step(p, s));
      await attempt('works_on_a_phone', async () => { await p.setViewportSize({ width: 375, height: 740 }); const bad = [];
        for (const w of SPEC.pages || ['']) { if (w) await open(p, w); else await p.goto(base + '/');
          await p.screenshot({ path: `${outDir}/${(w || 'home').replace(/\W/g, '')}-phone.png`, fullPage: true });
          if (await p.evaluate(() => document.documentElement.scrollWidth - innerWidth) > 2) bad.push(w || 'home'); }
        await p.setViewportSize({ width: 1280, height: 800 }); return { pass: !bad.length, detail: bad.join(', ') }; });
    } else if (SPEC.after_restart) {
      await attempt('data_survives_restart', async () => { if (LOGIN) await login(p); return step(p, SPEC.after_restart); });
    }
  } catch (e) { check('examiner_finished', false, e.message); }
  check(phase === '1' ? 'no_server_errors' : 'no_server_errors_after_restart', errors.length === 0, errors.slice(0, 3).join('; '));
  await b.close(); console.log(JSON.stringify({ checks }));
})();
