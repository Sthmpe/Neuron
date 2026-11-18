// Screenshots of a real NEURON install's phone page (phone-size browser): home, a finished document job, the built app.
const { chromium } = require('playwright');
const [base, code, out] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto(base + '/');
  await p.waitForSelector('#code');
  await p.fill('#code', code);
  await p.click('#pair');
  await p.waitForSelector('.item');
  await p.screenshot({ path: `${out}/1-home.png`, fullPage: true });
  const items = await p.$$eval('.item', els => els.map(e => ({ href: e.getAttribute('href'), t: e.innerText })));
  const word = items.find(i => /letter\.docx/i.test(i.t));
  const app = items.find(i => /bookshop/i.test(i.t));
  for (const [it, name] of [[word, '2-word-job'], [app, '3-app-job']]) {
    if (!it) continue;
    await p.goto(base + '/' + it.href);
    await p.waitForSelector('.steps');
    await p.waitForTimeout(500);
    await p.screenshot({ path: `${out}/${name}.png`, fullPage: true });
  }
  if (app) {
    await p.goto(base + '/' + app.href);
    await p.waitForSelector('#preview');
    await p.click('#preview');
    await p.waitForSelector('input[name=username]');
    await p.screenshot({ path: `${out}/4-app-login.png`, fullPage: true });
  }
  console.log(JSON.stringify(items.map(i => i.t.split('\n')[0]).slice(0, 8)));
  await b.close();
})();
