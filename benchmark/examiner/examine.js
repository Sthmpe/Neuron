// The examiner: uses a real browser like a person would. It never looks at the app's code.
//   node examine.js <task.json> <base url> <phase 1|2> <output folder>
// Phase 1 = fresh app. Phase 2 = after the app has been stopped and started again.
// Prints JSON: {checks: [{id, pass, detail}], screenshots: [...]}
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const [taskFile, base, phase, outDir] = process.argv.slice(2);
const task = JSON.parse(fs.readFileSync(taskFile, 'utf8'));
const checks = [], shots = [], serverErrors = [], pageErrors = [];
const rx = (s) => new RegExp(s, 'i');
const check = (id, pass, detail = '') => checks.push({ id, pass: !!pass, detail: String(detail).slice(0, 300) });

async function attempt(id, fn) {
  try { const r = await fn(); check(id, r === undefined ? true : r.pass ?? r, r && r.detail); }
  catch (e) { check(id, false, e.message.split('\n')[0]); }
}
async function bodyText(page) { return (await page.locator('body').innerText()).replace(/ /g, ' '); }
async function shot(page, name) {
  const file = `${outDir}/${name}.png`;
  try { await page.screenshot({ path: file, fullPage: true }); shots.push(file); } catch (e) { /* a screenshot never decides a check */ }
}
async function overflow(page) { return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); }
async function hasPasswordField(page) { return (await page.locator('input[type=password]:visible').count()) > 0; }

async function findField(page, label) {
  const tries = [page.getByLabel(rx(label)), page.locator(`input[name*="${label}" i], textarea[name*="${label}" i]`),
                 page.getByPlaceholder(rx(label))];
  for (const loc of tries) {
    const n = await loc.count();
    for (let i = 0; i < n; i++) if (await loc.nth(i).isVisible()) return loc.nth(i);
  }
  return null;
}
async function fillForm(page, record) {
  let last = null;
  for (const [label, value] of Object.entries(record)) {
    let field = await findField(page, label);
    if (!field) {   // maybe the form is behind an "Add ..." link
      const add = page.getByRole('link', { name: /add|new|create/i }).first();
      if (await add.count()) { await add.click(); await page.waitForLoadState(); field = await findField(page, label); }
    }
    if (!field) throw new Error(`no field for "${label}"`);
    await field.fill(value);
    last = field;
  }
  const form = last.locator('xpath=ancestor::form[1]');
  const button = form.locator('button[type=submit], input[type=submit], button:not([type])').first();
  if (await button.count()) await button.click(); else await last.press('Enter');
  await page.waitForLoadState();
}
async function login(page, creds) {
  await page.goto(base + '/');
  if (!(await hasPasswordField(page))) {
    const link = page.getByRole('link', { name: /log ?in|sign ?in/i }).first();
    if (await link.count()) { await link.click(); await page.waitForLoadState(); }
  }
  const user = (await findField(page, 'user')) || (await findField(page, 'name')) || page.locator('input[type=text], input:not([type])').first();
  await user.fill(creds.username);
  await page.locator('input[type=password]').first().fill(creds.password);
  await page.locator('input[type=password]').first().press('Enter');
  await page.waitForLoadState();
}
async function openEntity(page, link) {
  const a = page.getByRole('link', { name: rx(link) }).first();
  if (await a.count() && await a.isVisible()) { await a.click(); }
  else {
    const toggle = page.locator('label.nav-toggle, button[aria-label*=menu i]').first();
    if (await toggle.count() && await toggle.isVisible()) { await toggle.click(); }
    if (await a.count() && await a.isVisible()) await a.click(); else await page.goto(base + '/' + link);
  }
  await page.waitForLoadState();
}
async function openDashboard(page) {
  await page.goto(base + '/');
  await page.waitForLoadState();
}
function statShown(text, label, value) {
  const l = label.replace(/\s+/g, '\\s+');
  // the number right after the label (words may sit in between, another number may not), or right before it
  return new RegExp(`${l}[^0-9]{0,40}${value}(?![0-9])`, 'i').test(text) || new RegExp(`(?<![0-9])${value}[^0-9]{0,30}${l}`, 'i').test(text);
}

async function examineApp(browser) {
  const app = task.app;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('response', r => { if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url().replace(base, '')}`); });
  page.on('pageerror', e => pageErrors.push(e.message));
  if (phase === '1') {
    await attempt('app_opens', async () => { const r = await page.goto(base + '/'); return { pass: r && r.status() < 500, detail: r && r.status() }; });
    await attempt('login_is_required', async () => {
      await page.goto(base + '/'); if (await hasPasswordField(page)) return true;
      await page.goto(base + '/' + app.entities[0].link);
      return { pass: await hasPasswordField(page), detail: 'the records page opened without logging in' };
    });
    await shot(page, 'login-desktop');
    await attempt('wrong_password_is_rejected', async () => {
      await login(page, { username: app.login.username, password: 'definitely-wrong' });
      await page.goto(base + '/' + app.entities[0].link);
      return { pass: await hasPasswordField(page), detail: 'got in with a wrong password' };
    });
    await attempt('login_works', async () => { await login(page, app.login); await page.goto(base + '/'); return { pass: !(await hasPasswordField(page)), detail: 'still on the login form' }; });
    await attempt('dashboard_shows_the_requested_numbers', async () => {
      await openDashboard(page); const t = await bodyText(page);
      const missing = app.dashboard.filter(d => !rx(d.label).test(t)).map(d => d.label);
      return { pass: missing.length === 0, detail: 'no sign of: ' + missing.join(', ') };
    });
    for (const e of app.entities) {
      await attempt(`${e.link}_page_opens`, async () => { await openEntity(page, e.link); const t = await bodyText(page); return { pass: rx(e.link).test(t) && !(await hasPasswordField(page)), detail: page.url() }; });
      await attempt(`${e.link}_can_be_added`, async () => {
        for (const rec of e.records) { await openEntity(page, e.link); await fillForm(page, rec); }
        await openEntity(page, e.link); const t = await bodyText(page);
        const missing = e.records.map(r => Object.values(r)[0]).filter(v => !t.includes(v));
        return { pass: missing.length === 0, detail: 'not listed after adding: ' + missing.join(', ') };
      });
      await attempt(`${e.link}_search_works`, async () => {
        await openEntity(page, e.link);
        let box = page.getByRole('searchbox').first();
        if (!(await box.count())) box = page.locator('input[name=q], input[name*=search i], input[placeholder*=search i]').first();
        if (!(await box.count())) throw new Error('no search box');
        await box.fill(e.search.term); await box.press('Enter'); await page.waitForLoadState();
        const t = await bodyText(page);
        return { pass: t.includes(e.search.hit) && !t.includes(e.search.miss), detail: `hit shown: ${t.includes(e.search.hit)}, other record hidden: ${!t.includes(e.search.miss)}` };
      });
      await openEntity(page, e.link); await shot(page, `${e.link}-desktop`);
    }
    await attempt('dashboard_counts_are_right', async () => {
      await openDashboard(page); const t = await bodyText(page);
      const wrong = app.dashboard.filter(d => !statShown(t, d.label, d.value)).map(d => `${d.label} should be ${d.value}`);
      return { pass: wrong.length === 0, detail: wrong.join('; ') };
    });
    await openDashboard(page); await shot(page, 'dashboard-desktop');
    await attempt('works_on_a_phone', async () => {
      await page.setViewportSize({ width: 375, height: 740 });
      const bad = [];
      await openDashboard(page); if (await overflow(page) > 2) bad.push('dashboard'); await shot(page, 'dashboard-phone');
      for (const e of app.entities) { await page.goto(base + '/'); await openEntity(page, e.link); if (await overflow(page) > 2) bad.push(e.link); await shot(page, `${e.link}-phone`); }
      const meta = await page.locator('meta[name=viewport]').count();
      await page.setViewportSize({ width: 1280, height: 800 });
      return { pass: bad.length === 0 && meta > 0, detail: bad.length ? 'sideways scrolling on: ' + bad.join(', ') : 'no viewport setting' };
    });
  } else {
    await attempt('login_still_works_after_restart', async () => { await login(page, app.login); await page.goto(base + '/'); return !(await hasPasswordField(page)); });
    await attempt('records_survive_a_restart', async () => {
      const missing = [];
      for (const e of app.entities) { await openEntity(page, e.link); const t = await bodyText(page); for (const r of e.records) if (!t.includes(Object.values(r)[0])) missing.push(Object.values(r)[0]); }
      return { pass: missing.length === 0, detail: 'gone after restart: ' + missing.join(', ') };
    });
    await attempt('dashboard_right_after_restart', async () => {
      await openDashboard(page); const t = await bodyText(page);
      const wrong = app.dashboard.filter(d => !statShown(t, d.label, d.value)).map(d => `${d.label} should be ${d.value}`);
      return { pass: wrong.length === 0, detail: wrong.join('; ') };
    });
    await attempt('logout_works', async () => {
      await openDashboard(page);
      const out = page.getByRole('link', { name: /log ?out|sign ?out/i }).or(page.getByRole('button', { name: /log ?out|sign ?out/i })).first();
      if (!(await out.count())) throw new Error('no log out control');
      if (!(await out.isVisible())) { const toggle = page.locator('label.nav-toggle').first(); if (await toggle.count()) await toggle.click(); }
      await out.click(); await page.waitForLoadState();
      await page.goto(base + '/' + app.entities[0].link);
      return { pass: await hasPasswordField(page), detail: 'records page still open after logging out' };
    });
  }
  check(phase === '1' ? 'no_server_errors' : 'no_server_errors_after_restart', serverErrors.length === 0 && pageErrors.length === 0, [...serverErrors, ...pageErrors].slice(0, 4).join('; '));
  await ctx.close();
}

async function examineSite(browser) {
  const site = task.site;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('response', r => { if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url().replace(base, '')}`); });
  page.on('pageerror', e => pageErrors.push(e.message));
  if (phase === '1') {
    await attempt('page_opens', async () => { const r = await page.goto(base + '/'); return { pass: r && r.status() === 200, detail: r && r.status() }; });
    await attempt('headline_has_the_name', async () => {
      const heads = (await page.locator('h1, h2').allInnerTexts()).join(' | ');
      return { pass: rx(site.name).test(heads), detail: 'headlines: ' + heads };
    });
    const text = await bodyText(page).catch(() => '');
    for (const need of site.must_show) check(`shows_${need.replace(/[^a-z0-9]+/gi, '_')}`, rx(need).test(text), 'not found on the page');
    await shot(page, 'home-desktop');
    await attempt('looks_right_on_a_phone', async () => {
      await page.setViewportSize({ width: 375, height: 740 }); await page.goto(base + '/');
      const o = await overflow(page); const meta = await page.locator('meta[name=viewport]').count();
      await shot(page, 'home-phone'); await page.setViewportSize({ width: 1280, height: 800 });
      return { pass: o <= 2 && meta > 0, detail: o > 2 ? `page is ${o}px wider than the phone screen` : 'no viewport setting' };
    });
    await attempt('form_can_be_sent_and_thanks_shown', async () => {
      await page.goto(base + '/'); await fillForm(page, site.form);
      const t = await bodyText(page); await shot(page, 'after-form-desktop');
      return { pass: rx(site.thanks).test(t), detail: 'no thank-you message after sending' };
    });
  } else {
    await attempt('page_opens_after_restart', async () => { const r = await page.goto(base + '/'); const heads = (await page.locator('h1, h2').allInnerTexts()).join(' '); return { pass: r.status() === 200 && rx(site.name).test(heads) }; });
  }
  check(phase === '1' ? 'no_server_errors' : 'no_server_errors_after_restart', serverErrors.length === 0 && pageErrors.length === 0, [...serverErrors, ...pageErrors].slice(0, 4).join('; '));
  await ctx.close();
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  try { await (task.kind === 'app' ? examineApp(browser) : examineSite(browser)); }
  catch (e) { check('examiner_could_finish', false, e.message.split('\n')[0]); }
  await browser.close();
  console.log(JSON.stringify({ checks, screenshots: shots }));
})();
