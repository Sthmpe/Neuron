// The designer's eye, as rules. Renders each page at phone, tablet and desktop width and reports
// what a designer would notice. Arg: JSON {url, paths, login:[user,pass]|null, shots: prefix|null}
// Prints JSON {findings:[{rule, severity, width, path, detail}], pages:n}
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const zlib = require('zlib');

// Minimal PNG decoder (8-bit RGB/RGBA, not interlaced), so the checker can look at the rendered pixels.
function decodePNG(buf) {
  let pos = 8, w = 0, h = 0, ct = 0; const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos); const type = buf.toString('ascii', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') { w = data.readUInt32BE(0); h = data.readUInt32BE(4); ct = data[9]; }
    else if (type === 'IDAT') idat.push(data); else if (type === 'IEND') break;
    pos += 12 + len;
  }
  const bpp = ct === 6 ? 4 : 3; const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = w * bpp; const out = Buffer.alloc(h * stride); let prev = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)]; const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)); const cur = out.subarray(y * stride, (y + 1) * stride);
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? cur[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0; let v = line[i];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c); }
      cur[i] = v & 255;
    }
    prev = cur;
  }
  return { w, h, bpp, data: out };
}
const hex2rgb = (h) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));

// What share of the page each colour role covers, and how much of the page is calm empty space.
function lookAt(png, roles) {
  const { w, h, bpp, data } = png; const counts = {}; let total = 0, blankRows = 0;
  const near = (r, g, b, c) => Math.abs(r - c[0]) + Math.abs(g - c[1]) + Math.abs(b - c[2]) < 30;
  for (let y = 0; y < h; y += 2) {
    let first = null, uniform = true;
    for (let x = 0; x < w; x += 2) {
      const i = (y * w + x) * bpp; const r = data[i], g = data[i + 1], b = data[i + 2];
      if (first === null) first = [r, g, b]; else if (Math.abs(r - first[0]) + Math.abs(g - first[1]) + Math.abs(b - first[2]) > 12) uniform = false;
      total++;
      for (const [name, c] of Object.entries(roles)) if (near(r, g, b, c)) { counts[name] = (counts[name] || 0) + 1; break; }
    }
    if (uniform) blankRows++;
  }
  const share = {}; for (const k of Object.keys(roles)) share[k] = Math.round(1000 * (counts[k] || 0) / total) / 10;
  return { share, calm: Math.round(1000 * blankRows / Math.ceil(h / 2)) / 10 };
}
const a = JSON.parse(process.argv[2]);
const WIDTHS = [[390, 844, 'phone'], [768, 1024, 'tablet'], [1280, 800, 'desktop']];

const PROBE = () => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const rgba = (css) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = css; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const lum = ([r, g, b]) => { const f = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (x, y) => { const [h, l] = [lum(x), lum(y)].sort((p, q) => q - p); return (h + 0.05) / (l + 0.05); };
  const over = (top, under) => [0, 1, 2].map(i => top[i] * top[3] + under[i] * (1 - top[3])).concat([1]);
  const bgOf = (el) => {
    const chain = []; for (let e = el; e; e = e.parentElement) chain.push(e);
    let acc = [255, 255, 255, 1];
    for (const e of chain.reverse()) {
      const st = getComputedStyle(e);
      if (st.backgroundImage && st.backgroundImage !== 'none') return null;   // gradients or images: not judged here
      const c = rgba(st.backgroundColor); if (c[3] > 0) acc = over(c, acc);
    }
    return acc;
  };
  const visible = (el) => { const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none' && parseFloat(st.opacity) > 0.05; };
  const name = (el) => (el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '')
    + ' "' + (el.innerText || el.value || '').trim().slice(0, 30) + '"');
  const out = [];
  const add = (rule, severity, detail) => out.push({ rule, severity, detail });
  const W = innerWidth;
  // 1. sideways scrolling
  const ov = document.documentElement.scrollWidth - W;
  if (ov > 1) add('overflow', 'fail', `page is ${ov}px wider than the screen`);
  // 2. contrast + 3. small text
  const texts = [...document.querySelectorAll('body *')].filter(el => visible(el) &&
    [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1));
  const bodySizes = [];
  for (const el of texts) {
    const st = getComputedStyle(el); const fs = parseFloat(st.fontSize); const fw = parseInt(st.fontWeight);
    if (el.closest('.skip')) continue;
    if (el.tagName === 'P') bodySizes.push(fs);
    if (fs < 12) add('small_text', 'fail', `${name(el)} is ${fs}px`);
    const bg = bgOf(el); if (!bg) continue;
    const fg = over(rgba(st.color), bg);
    const large = fs >= 24 || (fs >= 18.66 && fw >= 700);
    const r = ratio(fg, bg); const need = large ? 3 : 4.5;
    if (r < need) add('contrast', 'fail', `${name(el)} ${r.toFixed(2)}:1, needs ${need}:1`);
  }
  // placeholders and input text against their own fields
  // 4. tap targets on phones
  if (W < 600) for (const el of document.querySelectorAll('a.btn, button, input:not([type=hidden]), select, textarea, .menu a, label.nav-toggle')) {
    if (!visible(el)) continue; const r = el.getBoundingClientRect();
    if (r.height < 40 || r.width < 40) add('tap_target', 'fail', `${name(el)} is ${Math.round(r.width)}x${Math.round(r.height)}px`);
  }
  // 5. line length
  for (const p of document.querySelectorAll('main p')) {
    if (!visible(p)) continue; const st = getComputedStyle(p);
    const cpl = p.getBoundingClientRect().width / (parseFloat(st.fontSize) * 0.5);
    if (cpl > 95 && (p.innerText || '').length > 120) add('line_length', 'warn', `${name(p)} runs about ${Math.round(cpl)} characters per line`);
  }
  // 6. hierarchy
  const h1s = [...document.querySelectorAll('h1')].filter(visible);
  const base = bodySizes.length ? bodySizes.sort((x, y) => x - y)[Math.floor(bodySizes.length / 2)] : 16;
  if (h1s.length !== 1) add('hierarchy', 'fail', `${h1s.length} main headings (h1) on the page; there should be exactly one`);
  if (h1s.length) {
    const s1 = parseFloat(getComputedStyle(h1s[0]).fontSize);
    if (s1 < base * 1.5) add('hierarchy', 'fail', `main heading ${s1}px is not clearly bigger than body text ${base}px`);
    for (const h2 of [...document.querySelectorAll('h2')].filter(visible))
      if (parseFloat(getComputedStyle(h2).fontSize) >= s1 + 0.5 && !h2.classList.contains('fact-text'))
        add('hierarchy', 'fail', `${name(h2)} is as big as the main heading`);
  }
  // 7. one main action per screen
  const prim = [...document.querySelectorAll('.btn-primary')].filter(el => { if (!visible(el)) return false;
    const r = el.getBoundingClientRect(); return r.top + scrollY < innerHeight; });
  if (prim.length > 1) add('main_action', 'fail', `${prim.length} primary buttons in the first screen: ${prim.map(name).join(', ')}`);
  if (document.querySelector('.hero') && prim.length === 0) add('main_action', 'fail', 'the first screen has no main action');
  // 8. no border lines (taste)
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue; const st = getComputedStyle(el);
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      const w = parseFloat(st[`border${side}Width`]);
      if (w > 0 && st[`border${side}Style`] !== 'none' && rgba(st[`border${side}Color`])[3] > 0.05) {
        add('border_line', 'fail', `${name(el)} has a ${w}px border line`); break; }
    }
  }
  // 9. crowding: padded boxes must give their text room; blocks must not overlap
  for (const el of document.querySelectorAll('.card, .f-card, .f-tile, .fr-item, .form-card, .stat, .hero-visual, .hc-card, .fp-card, .alert')) {
    if (!visible(el)) continue; const st = getComputedStyle(el);
    const pad = Math.min(...['Top', 'Right', 'Bottom', 'Left'].map(s => parseFloat(st[`padding${s}`])));
    if (pad < 12) add('crowding', 'fail', `${name(el)} has only ${pad}px of padding`);
  }
  const blocks = [...document.querySelectorAll('main h1, main h2, main h3, main p, main .btn, main input, main .icon-wrap')].filter(visible);
  for (let i = 0; i < blocks.length; i++) for (let j = i + 1; j < blocks.length; j++) {
    const x = blocks[i], y = blocks[j]; if (x.contains(y) || y.contains(x)) continue;
    const r = x.getBoundingClientRect(), q = y.getBoundingClientRect();
    const ix = Math.min(r.right, q.right) - Math.max(r.left, q.left), iy = Math.min(r.bottom, q.bottom) - Math.max(r.top, q.top);
    if (ix > 4 && iy > 4) add('overlap', 'fail', `${name(x)} overlaps ${name(y)}`);
  }
  for (const s of document.querySelectorAll('main > section, main > .section')) {
    const st = getComputedStyle(s);
    if (parseFloat(st.paddingTop) < 32 && s.getBoundingClientRect().height > 100) add('crowding', 'fail', `${name(s)} has only ${st.paddingTop} above it`);
  }
  // 10. em dashes anywhere in the visible text
  const t = document.body.innerText;
  if (/[—―]/.test(t)) add('em_dash', 'fail', 'the page shows an em dash');
  // 12. one clear focal point per screen: within each screen-height slice, the biggest text should be one thing
  if (W >= 1200) {
    const heads = [...document.querySelectorAll('main h1, main h2, main .fact-text, main .stat-value')].filter(visible)
      .map(e => ({ e, fs: parseFloat(getComputedStyle(e).fontSize), top: e.getBoundingClientRect().top + scrollY }));
    for (let y0 = 0; y0 < document.documentElement.scrollHeight; y0 += innerHeight) {
      const inside = heads.filter(x => x.top >= y0 && x.top < y0 + innerHeight);
      if (!inside.length) continue;
      const max = Math.max(...inside.map(x => x.fs));
      const top = inside.filter(x => Math.abs(x.fs - max) < 1 && !x.e.classList.contains('stat-value'));
      if (top.length > 1) add('focal_point', 'warn', `${top.length} equally big headings compete in one screen: ${top.map(x => name(x.e)).join(', ')}`);
    }
  }
  // 11. alignment: left edges of the main reading blocks on wide screens
  if (W >= 1200) {
    const edges = new Set(blocks.filter(b => ['H1', 'H2', 'P'].includes(b.tagName) && getComputedStyle(b).textAlign !== 'center')
      .map(b => Math.round(b.getBoundingClientRect().left / 6)));
    if (edges.size > 7) add('alignment', 'warn', `${edges.size} different left edges for headings and text`);
  }
  return out;
};

(async () => {
  const b = await chromium.launch();
  const findings = [];
  for (const [w, h, label] of WIDTHS) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    if (a.login) { await p.goto(a.url + '/login'); await p.fill('input[name=username]', a.login[0]);
      await p.fill('input[name=password]', a.login[1]); await p.press('input[name=password]', 'Enter'); await p.waitForLoadState(); }
    for (const path of a.paths) {
      try {
        await p.goto(a.url + path); await p.waitForLoadState('networkidle'); await p.evaluate(() => document.fonts.ready);
        for (const f of await p.evaluate(PROBE)) findings.push({ ...f, width: label, path });
        if (a.shots) await p.screenshot({ path: `${a.shots}-${path.replace(/\W/g, '') || 'home'}-${label}.png`, fullPage: true });
        if (a.roles && label === 'desktop') {        // look at the rendered pixels
          const look = lookAt(decodePNG(await p.screenshot({ fullPage: true })), Object.fromEntries(Object.entries(a.roles).map(([k, v]) => [k, hex2rgb(v)])));
          findings.push({ rule: 'colour_share', severity: 'info', width: label, path, detail: JSON.stringify(look) });
          if ((look.share.action || 0) > 12) findings.push({ rule: 'accent_overuse', severity: 'fail', width: label, path, detail: `the action colour covers ${look.share.action}% of the page; it should stay small` });
          const tones = (look.share.bg || 0) + (look.share.surface || 0) + (look.share.tone2 || 0);
          if (tones < 45) findings.push({ rule: 'no_dominant_tone', severity: 'warn', width: label, path, detail: `the main page tones cover only ${tones}%` });
          if (look.calm < 18) findings.push({ rule: 'crowding', severity: 'warn', width: label, path, detail: `only ${look.calm}% of the page height is calm empty space` });
        }
      } catch (e) { findings.push({ rule: 'page_error', severity: 'fail', width: label, path, detail: e.message.split('\n')[0] }); }
    }
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify({ findings, pages: a.paths.length }));
})();
