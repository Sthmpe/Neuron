// Review screenshots (JPEG, phone 390 px and desktop 1280 px). Arg: JSON {url, out, paths, login}
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const a = JSON.parse(process.argv[2]);
  const b = await chromium.launch();
  for (const [w, h, n] of [[390, 844, 'phone'], [1280, 800, 'desktop']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    if (a.login) { await p.goto(a.url + '/login'); await p.fill('input[name=username]', a.login[0]); await p.fill('input[name=password]', a.login[1]); await p.press('input[name=password]', 'Enter'); await p.waitForLoadState(); }
    for (const path of a.paths) {
      await p.goto(a.url + path); await p.waitForLoadState('networkidle'); await p.evaluate(() => document.fonts.ready);
      await p.screenshot({ path: `${a.out}-${path.replace(/\W/g, '') || 'home'}-${n}.jpg`, fullPage: true, type: 'jpeg', quality: 82 });
    }
    await ctx.close();
  }
  await b.close();
})();
