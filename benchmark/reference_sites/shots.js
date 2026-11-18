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
    await p.screenshot({ path: `${out}-${name}.png`, fullPage: true });
    res[name] = { overflow: await p.evaluate(() => document.documentElement.scrollWidth - innerWidth), broken: bad,
                  images: await p.evaluate(() => [...document.images].map(i => ({ src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0 }))) };
    if (name === 'desktop') res.text = await p.locator('main').innerText();   // the page's own words, not the menu or footer
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(res));
})();
