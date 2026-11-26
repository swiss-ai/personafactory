// Usage: node tools/preview.js <built index.html> <section id> <out dir> [--play]
// Screenshots one section (light 1280, dark 1280, phone 390) and reports layout problems:
// console errors, horizontal page scroll, text overflowing its box, SVG text outside its svg,
// and charts with 2+ colours but no legend nearby.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [file, sid, out] = process.argv.slice(2);
  const play = process.argv.includes('--play');
  if (!file || !sid || !out) { console.error('usage: node tools/preview.js <index.html> <section-id> <out-dir> [--play]'); process.exit(2); }
  const b = await chromium.launch();
  const report = {};
  for (const [name, opts] of [['light', { viewport: { width: 1280, height: 900 }, colorScheme: 'light' }], ['dark', { viewport: { width: 1280, height: 900 }, colorScheme: 'dark' }], ['phone', { viewport: { width: 390, height: 844 }, colorScheme: 'light' }]]) {
    const p = await b.newPage({ ...opts, reducedMotion: 'reduce' });
    const errs = [];
    p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    p.on('pageerror', e => errs.push(String(e)));
    await p.goto('file://' + path.resolve(file));
    await p.waitForTimeout(1200);
    const sec = await p.$('#' + sid);
    if (!sec) { console.log('section not found:', sid); process.exit(1); }
    await sec.scrollIntoViewIfNeeded();
    if (play) { const btn = await sec.$('[data-play]'); if (btn) { await btn.click(); await p.waitForTimeout(4000); } }
    await p.waitForTimeout(400);
    const issues = await p.evaluate((sid) => {
      const root = document.getElementById(sid); const out = [];
      const desc = el => { const id = el.id ? '#' + el.id : ''; const cls = el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : ''; return el.tagName.toLowerCase() + id + cls; };
      if (document.documentElement.scrollWidth > innerWidth + 1) out.push(`page scrolls horizontally: ${document.documentElement.scrollWidth} > ${innerWidth}`);
      root.querySelectorAll('*').forEach(el => {
        if (el.closest('svg')) return;
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        if (['auto', 'scroll'].includes(cs.overflowX) || cs.overflowX === 'hidden' && el.scrollWidth > el.clientWidth + 1 && el.closest('.factory-scroll')) return;
        if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && !['inline'].includes(cs.display)) {
          // only report if a child actually sticks out (not just inline overflow of auto containers)
          const inScroller = el.closest('[class*="scroll"], .tblwrap');
          if (!inScroller) out.push(`overflow: ${desc(el)} scrollWidth ${el.scrollWidth} > clientWidth ${el.clientWidth}`);
        }
      });
      root.querySelectorAll('svg').forEach(svg => {
        const vb = svg.viewBox && svg.viewBox.baseVal; if (!vb || !vb.width) return;
        svg.querySelectorAll('text').forEach(t => {
          if (!t.textContent.trim()) return;
          let bb; try { bb = t.getBBox(); } catch (e) { return; }
          const ctm = t.getCTM && t.getCTM(); const sctm = svg.getCTM && svg.getCTM();
          // compare in svg user space using screen rects
          const r = t.getBoundingClientRect(), s = svg.getBoundingClientRect();
          if (r.width && (r.left < s.left - 2 || r.right > s.right + 2)) out.push(`svg text outside svg: "${t.textContent.slice(0, 40)}" in ${desc(svg.parentElement)}`);
        });
        // text sticking out of a rect it sits on (labels inside boxes)
      });
      // charts with 2+ fill colours and no legend in the same card
      root.querySelectorAll('svg.viz').forEach(svg => {
        const fills = new Set(); svg.querySelectorAll('path,rect,circle').forEach(n => { const f = n.getAttribute('fill'); if (f && f.startsWith('var(--') && !/rule|tint|surface|paper|seq|on-strong/.test(f)) fills.add(f); });
        const card = svg.closest('.card, .panel, .readout, .line, .demo, figure, section');
        const hasLegend = card && card.querySelector('.legend');
        const isHeat = svg.querySelector('rect[fill^="color-mix"]');
        if (fills.size >= 2 && !hasLegend && !isHeat) out.push(`chart with ${fills.size} colours but no .legend: in ${desc(svg.parentElement)} (${[...fills].join(', ')})`);
      });
      // DOM text overflowing a fixed-size box: check children whose rect exceeds a .card/.line ancestor
      root.querySelectorAll('.card, .demo, .line, .panel').forEach(box => {
        const br = box.getBoundingClientRect();
        box.querySelectorAll('*').forEach(el => { const r = el.getBoundingClientRect(); if (r.width && (r.right > br.right + 2 || r.left < br.left - 2) && !el.closest('[class*="scroll"], .tblwrap')) { out.push(`sticks out of ${desc(box)}: ${desc(el)} (${Math.round(r.left - br.left)}..${Math.round(r.right - br.left)} of ${Math.round(br.width)})`); } });
      });
      return [...new Set(out)].slice(0, 40);
    }, sid);
    report[name] = { errors: errs, issues };
    await sec.screenshot({ path: path.join(out, `${sid}-${name}.png`) });
    await p.close();
  }
  await b.close();
  console.log(JSON.stringify(report, null, 2));
  console.log('screenshots:', ['light', 'dark', 'phone'].map(n => path.join(out, `${sid}-${n}.png`)).join(' '));
})();
