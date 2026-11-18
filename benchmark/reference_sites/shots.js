// Phone, tablet and desktop screenshots of a site's home page, plus the visible text and overflow per width.
//   node shots.js <url> <out prefix>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [url, out] = process.argv.slice(2);
  const b = await chromium.launch();
  const res = {};
  for (const [name, w, h] of [['phone', 390, 844], ['tablet', 820, 1180], ['desktop', 1440, 900]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    const bad = [];
    p.on('response', r => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url().replace(url, '')}`); });
    await p.goto(url + '/'); await p.waitForLoadState('networkidle');
    // pictures further down load only when a visitor scrolls to them: scroll down like a person (instant, not smooth),
    // wait until every picture has real pixels, then go back to the top before the full-page picture is taken
    await p.evaluate(async () => {
      document.documentElement.style.scrollBehavior = 'auto';
      for (let y = 0; y < document.body.scrollHeight; y += 300) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); }
    });
    await p.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth > 0), null, { timeout: 20000 }).catch(() => {});
    await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(400);
    await p.screenshot({ path: `${out}-${name}.png`, fullPage: true });
    res[name] = { overflow: await p.evaluate(() => document.documentElement.scrollWidth - innerWidth), broken: bad,
                  images: await p.evaluate(() => [...document.images].map(i => ({ src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0 }))) };
    if (name === 'desktop') res.text = await p.locator('main').innerText();   // the page's own words, not the menu or footer
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(res));
})();
