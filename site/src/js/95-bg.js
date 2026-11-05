/* ---------- background: the page is the shop floor, seen from above ----------
   One absolutely positioned SVG behind the whole page (z-index -1). It paints the chapter bands
   (so .sec no longer paints its own opaque fill), a blueprint grid in the side aisles, a painted
   walkway in the left aisle that opens a short corridor into every station, structural columns
   with dimension lines in the right aisle, hazard-tape thresholds where one band meets the next,
   and a huge worn stencil label in the empty strip above each heading. Nothing is drawn under the
   content column except the band fill and the stencil, which only sits in the padding above the
   heading. A small forklift (fixed, left aisle) faces the way you scroll. */
const FL_LABEL = { findings: 'ST-00 REPORT', bank: 'ST-01 ASSEMBLY', augment: 'ST-02 AUGMENT', corpus: 'ST-03 CORPUS', eval: 'ST-04 QC', ablations: 'ST-05 TUNING', downstream: 'ST-06 DOWNSTREAM', compare: 'ST-07 COMPARE', cite: 'ST-08 DISPATCH' };
const page = $('.page'), main = $('main');
if (page && main) {
  const floor = document.createElement('div');
  floor.className = 'floor'; floor.setAttribute('aria-hidden', 'true');
  document.body.prepend(floor);
  document.documentElement.classList.add('has-floor');

  // worn-paint texture: a seeded speckle tile, used as a luminance mask on everything "painted"
  function rng(seed){ let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
  const noise = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 180; const g = c.getContext('2d'); const r = rng(7);
    g.fillStyle = '#fff'; g.fillRect(0, 0, 180, 180);
    for (let i = 0; i < 340; i++) { g.fillStyle = `rgba(0,0,0,${0.18 + r() * 0.6})`; g.beginPath(); g.ellipse(r() * 180, r() * 180, 0.4 + r() * 2.4, 0.4 + r() * 1.6, r() * 3.14, 0, 6.29); g.fill(); }
    g.lineCap = 'round';
    for (let i = 0; i < 14; i++) { g.strokeStyle = `rgba(0,0,0,${0.12 + r() * 0.25})`; g.lineWidth = 0.6 + r() * 1.6; const x = r() * 180, y = r() * 180, a = r() * 6.28, l = 18 + r() * 50; g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
    try { return c.toDataURL('image/png'); } catch (e) { return null; }
  })();

  // forklift: cruises in the walkway at a fixed height, faces the way you scroll, and at the end of
  // the route parks in front of the last station and turns in
  let forklift = null, laneX = 0, parkY = Infinity, place = () => {};
  if (!reduce) {
    forklift = document.createElement('div'); forklift.className = 'fl-truck'; forklift.setAttribute('aria-hidden', 'true');
    forklift.innerHTML = '<div class="tk-rot"><svg viewBox="0 0 20 38" width="20" height="38"><g class="tk-whl"><rect x="0" y="6" width="3" height="7" rx="1"/><rect x="17" y="6" width="3" height="7" rx="1"/><rect x="0" y="19" width="3" height="7" rx="1"/><rect x="17" y="19" width="3" height="7" rx="1"/></g><rect class="tk-cw" x="3" y="1" width="14" height="6" rx="2.5"/><rect class="tk-body" x="2.5" y="4" width="15" height="22" rx="2"/><rect class="tk-cab" x="5" y="9" width="10" height="10" rx="1.2"/><path class="tk-cage" d="M5 12h10M5 16h10"/><rect class="tk-mast" x="2" y="26" width="16" height="2.5" rx=".6"/><path class="tk-fork" d="M5.5 28.5v8.5M14.5 28.5v8.5"/></svg></div>';
    document.body.appendChild(forklift);
    let lastY = scrollY, up = false, raf2 = 0;
    place = () => {
      raf2 = 0; const y = scrollY;
      if (Math.abs(y - lastY) > 4) { up = y < lastY; lastY = y; }
      const cruise = innerHeight * 0.68, door = parkY - y - 19, parked = door < cruise;
      forklift.style.transform = `translate3d(${laneX}px, ${Math.round(parked ? door : cruise)}px, 0)`;
      forklift.dataset.dir = parked ? 'in' : up ? 'up' : 'down';
    };
    addEventListener('scroll', () => { if (!raf2) raf2 = requestAnimationFrame(place); }, { passive: true });
  }

  const bandEls = () => [$('.hero'), ...$$('main > section.sec')].filter(Boolean);

  // ---- gears: meshing trains seen from above, turned by scrolling (one rAF per scroll frame) ----
  const DEG = Math.PI / 180, R2 = v => Math.round(v * 100) / 100;
  let spin = [], floorTop = 0;
  function gearD(r, n, d){
    const ro = r + d / 2, ri = r - d / 2, st = 2 * Math.PI / n;
    const P = (a, rr) => R2(Math.cos(a) * rr) + ' ' + R2(Math.sin(a) * rr);
    let o = '';
    for (let i = 0; i < n; i++){
      const a = i * st;
      o += (i ? ` A${R2(ri)} ${R2(ri)} 0 0 1 ` : 'M') + P(a - .25 * st, ri) + ' L' + P(a - .12 * st, ro) + ` A${R2(ro)} ${R2(ro)} 0 0 1 ` + P(a + .12 * st, ro) + ' L' + P(a + .25 * st, ri);
    }
    return o + ` A${R2(ri)} ${R2(ri)} 0 0 1 ` + P(-.25 * st, ri) + 'Z';
  }
  function gearEl(p, m, n, acc){
    const r = m * n / 2, g = S('g', { class: 'fl-gear' + (acc ? ' acc' : '') }, p);
    S('path', { d: gearD(r, n, m * 1.15), class: 'fl-gbody' }, g);
    const rim = r - m * 1.15 / 2 - Math.max(2.5, r * .1);
    if (r >= 26){
      S('circle', { r: R2(rim), class: 'fl-gln' }, g);
      const hub = r * .24;
      for (let i = 0; i < 5; i++){ const a = i * 72 * DEG, c = Math.cos(a), sn = Math.sin(a), w = Math.max(1.6, r * .045);
        S('path', { class: 'fl-gln', d: `M${R2(c * hub - sn * w)} ${R2(sn * hub + c * w)}L${R2(c * rim - sn * w)} ${R2(sn * rim + c * w)}M${R2(c * hub + sn * w)} ${R2(sn * hub - c * w)}L${R2(c * rim + sn * w)} ${R2(sn * rim - c * w)}` }, g); }
      S('circle', { r: R2(hub), class: 'fl-gln' }, g);
    } else if (r >= 12){
      for (let i = 0; i < 4; i++){ const a = (i * 90 + 45) * DEG; S('circle', { cx: R2(Math.cos(a) * r * .52), cy: R2(Math.sin(a) * r * .52), r: R2(r * .15), class: 'fl-gln' }, g); }
      S('circle', { r: R2(r * .22), class: 'fl-gln' }, g);
    } else S('circle', { r: R2(Math.max(2.2, r * .3)), class: 'fl-gln' }, g);
    S('circle', { r: R2(Math.max(1.2, r * .08)), class: 'fl-gaxle' }, g);
    return g;
  }
  // spec: [[teeth, direction from previous gear (deg)], ...]; acc = index of the gear painted orange
  function trainAt(p, x, y, m, spec, speed, acc = -1){
    let prev = null; const out = [];
    spec.forEach(([n, dir], i) => {
      const r = m * n / 2; let cx = x, cy = y, ph = 0, ratio = 1;
      if (prev){
        cx = prev.x + Math.cos(dir * DEG) * (prev.r + r); cy = prev.y + Math.sin(dir * DEG) * (prev.r + r);
        ratio = -prev.ratio * prev.n / n;
        const pitch = 360 / prev.n, dA = ((dir - prev.ph) % pitch + pitch) % pitch;
        ph = dir + 180 + dA * prev.n / n + 180 / n;   // a tooth of this gear sits in a gap of the previous one
      }
      const g = gearEl(p, m, n, i === acc);
      const it = { g, x: cx, y: cy, r, n, ph, ratio: ratio, k: speed };
      g.setAttribute('transform', `translate(${R2(cx)} ${R2(cy)}) rotate(${R2(ph)})`);
      spin.push(it); out.push(it); prev = it;
    });
    return out;
  }
  let gearRaf = 0, lastA = {};
  function turn(){
    gearRaf = 0; if (reduce) return;
    const y0 = scrollY - floorTop - 240, y1 = y0 + innerHeight + 480;
    spin.forEach(it => {
      if (it.y < y0 || it.y > y1) return;
      const a = Math.round((it.ph + scrollY * it.k * it.ratio) * 10) / 10;
      if (it.a === a) return; it.a = a;
      it.g.setAttribute('transform', `translate(${R2(it.x)} ${R2(it.y)}) rotate(${a})`);
    });
  }
  if (!reduce) addEventListener('scroll', () => { if (!gearRaf) gearRaf = requestAnimationFrame(turn); }, { passive: true });

  const r1 = v => Math.round(v * 10) / 10;

  function draw(){
    const W = document.documentElement.clientWidth;
    const top0 = page.getBoundingClientRect().top + scrollY;
    const H = Math.ceil(page.getBoundingClientRect().bottom + scrollY);
    const mb = main.getBoundingClientRect();
    const L = Math.round(mb.left), R = Math.round(mb.right);   // content column edges
    const aisle = L;                                            // aisle (gutter) width
    const wide = aisle >= 72;
    const laneC = Math.round(Math.min(Math.max(aisle * 0.38, 30), 96));  // walkway centre line
    const lane1 = laneC - 12, lane2 = laneC + 12;
    const colX = Math.round(W - Math.min(aisle * 0.48, 104));           // column centre line
    spin = []; floorTop = top0;
    floor.style.top = top0 + 'px'; floor.style.height = (H - top0) + 'px';
    const svg = S('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    const defs = S('defs', {}, svg);

    // patterns: blueprint grid (24px minor, 120px major), hazard stripes, keep-clear hatch
    const gp = S('pattern', { id: 'flGrid', width: 120, height: 120, patternUnits: 'userSpaceOnUse', x: L, y: 0 }, defs);
    let d = '';
    for (let i = 24; i < 120; i += 24) d += `M${i} 0V120M0 ${i}H120`;
    S('path', { d, class: 'fl-gmin' }, gp);
    S('path', { d: 'M0 0V120M0 0H120', class: 'fl-gmaj' }, gp);
    const hz = S('pattern', { id: 'flHaz', width: 16, height: 16, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, defs);
    S('rect', { width: 8, height: 16, class: 'fl-hz' }, hz);
    const hp = S('pattern', { id: 'flHatch', width: 9, height: 9, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(-45)' }, defs);
    S('rect', { width: 2.2, height: 9, class: 'fl-hatch' }, hp);
    // grid visible in the aisles only: fades out before the content column on both sides
    const lg = S('linearGradient', { id: 'flGridFade', gradientUnits: 'userSpaceOnUse', x1: 0, x2: W, y1: 0, y2: 0 }, defs);
    const f = v => Math.max(0, Math.min(1, v / W));
    [[0, 1], [f(L - 56), 1], [f(L - 6), 0], [f(R + 6), 0], [f(R + 56), 1], [1, 1]].forEach(([o, a]) => S('stop', { offset: o, 'stop-color': '#fff', 'stop-opacity': a }, lg));
    const gm = S('mask', { id: 'flGridMask', maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: W, height: H }, defs);
    S('rect', { width: W, height: H, fill: 'url(#flGridFade)' }, gm);
    if (noise) {
      const np = S('pattern', { id: 'flNoise', width: 180, height: 180, patternUnits: 'userSpaceOnUse' }, defs);
      S('image', { href: noise, width: 180, height: 180 }, np);
      const wm = S('mask', { id: 'flWear', maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: W, height: H }, defs);
      S('rect', { width: W, height: H, fill: 'url(#flNoise)' }, wm);
    }

    const gBands = S('g', {}, svg);
    if (L >= 64) S('rect', { width: W, height: H, fill: 'url(#flGrid)', mask: 'url(#flGridMask)' }, svg);  // no grid stubs in a narrow gutter
    const gHw = S('g', { class: 'fl-hw' }, svg);                              // hardware: columns, grates, bolts
    const gPaint = S('g', { class: 'fl-paint', mask: noise ? 'url(#flWear)' : null }, svg);  // paint: worn
    const gBridge = S('g', {}, svg);

    // a bolted housing, open from above, with a three-gear train standing on its long axis
    function gearbox(g, seed){
      const w = 50, h = 132;
      S('rect', { x: -w / 2, y: -h / 2, width: w, height: h, rx: 3, class: 'fl-plate' }, g);
      S('rect', { x: -w / 2 + 5, y: -h / 2 + 5, width: w - 10, height: h - 10, rx: 2, class: 'fl-dim dash' }, g);
      [[-w / 2 + 4, -h / 2 + 4], [w / 2 - 4, -h / 2 + 4], [-w / 2 + 4, h / 2 - 4], [w / 2 - 4, h / 2 - 4]].forEach(([x, y]) => S('circle', { cx: x, cy: y, r: 1.5, class: 'fl-bolt' }, g));
      const m = 2;
      const spec = seed % 2 ? [[17, 0], [9, 80], [14, 100]] : [[14, 0], [10, 96], [16, 84]];
      // centre the train vertically in the housing
      const r0 = m * spec[0][0] / 2, r1 = m * spec[1][0] / 2, r2 = m * spec[2][0] / 2;
      trainAt(g, 0, -(r0 + r1 + r2) + r0, m, spec, 0.11, 1);
    }

    const bands = bandEls().map(el => {
      const b = el.getBoundingClientRect(); const h2 = el.querySelector('h2');
      const hb = h2 ? h2.getBoundingClientRect() : null;
      return { el, id: el.id, top: Math.round(b.top + scrollY - top0), h: Math.round(b.height), sec: el.classList.contains('sec'), alt: el.classList.contains('alt'),
               hTop: hb ? hb.top - b.top : 0, hMid: hb ? hb.top + Math.min(hb.height, 48) / 2 - b.top : 0 };
    });
    // the page starts at the very top: let the hero's floor run up under the header
    if (bands[0] && !bands[0].sec) { bands[0].h += bands[0].top; bands[0].top = 0; }

    // 1. band fills + their top rule (what .sec's border-image used to paint)
    bands.forEach(b => {
      if (!b.sec) return;
      S('rect', { x: 0, y: b.top, width: W, height: b.h, class: 'fl-band' + (b.alt ? ' alt' : '') }, gBands);
      S('rect', { x: 0, y: b.top, width: W, height: 1, class: 'fl-rule' }, gBands);
    });

    // 2. stencil labels in the strip above each heading, cropped by the band's top edge
    const fs = Math.round(Math.min(Math.max(W * 0.08, 54), 106));
    const stencils = [];
    bands.forEach(b => {
      const lab = FL_LABEL[b.id]; if (!lab || !b.sec) return;
      const cp = S('clipPath', { id: 'flc-' + b.id }, defs);
      S('rect', { x: 0, y: b.top + 1, width: W, height: Math.max(0, b.hTop - 10) }, cp);
      const base = b.top + Math.round(Math.min(b.hTop - 18, fs * 0.7));
      const t = T(lab, { x: R + Math.round(fs * 0.04), y: base, 'text-anchor': 'end', class: 'fl-stencil' + (b.alt ? ' alt' : ''), 'font-size': fs, 'clip-path': `url(#flc-${b.id})` }, gPaint);
      stencils.push({ t, lab, b });
    });
    // band colour at a given floor y (for pads that must hide the grid behind a label)
    const altAt = y => { const b = bands.find(b => b.sec && y >= b.top && y < b.top + b.h); return b ? b.alt : false; };

    // 3. hazard-tape thresholds where one band meets the next (aisles only, and only where there is room)
    bands.forEach(b => {
      if (!b.sec) return;
      const y = b.top - 5;
      if (L - 10 >= 40) S('rect', { x: 0, y, width: L - 10, height: 10, fill: 'url(#flHaz)', class: 'fl-tape' }, gPaint);
      if (W - R - 10 >= 40) S('rect', { x: R + 10, y, width: W - R - 10, height: 10, fill: 'url(#flHaz)', class: 'fl-tape' }, gPaint);
    });

    if (wide) {
      // 4. walkway: two dashed lines down the left aisle; the inner line opens a corridor into each
      //    station, and the route ends by turning into the last one (dispatch)
      const doors = bands.filter(b => b.sec).map(b => ({ y: Math.round(b.top + b.hMid), b }));
      const xe = L - 14, last = doors[doors.length - 1];
      const endY = last ? last.y + 26 : H;
      const inner = [];
      let y0 = 0;
      doors.forEach(dr => { inner.push([y0, dr.y - 26]); y0 = dr.y + 26; });
      if (!last) inner.push([y0, H]);
      // all walkway tape shares one translucent group, so overlapping pieces never paint darker
      const gLane = S('g', { class: 'fl-lanes' }, gPaint);
      S('path', { d: `M${lane1} 0V${endY}` + (last ? `M${xe} ${endY}H${lane1}` : ''), class: 'fl-lane' }, gLane);
      S('path', { d: inner.map(([a, b]) => `M${lane2} ${a}V${b}`).join(''), class: 'fl-lane' }, gLane);
      // solid L-shaped corner pieces, as on real taped walkways: the dashes can never leave a corner open
      const ck = 10;
      let corners = last ? `M${lane1} ${endY - ck}V${endY}H${lane1 + ck}` : '';
      doors.forEach(dr => {
        if (xe - lane2 < 10) return;
        // corridor sides are drawn from the stop bar outwards, so the dash pattern always meets the bar
        S('path', { d: `M${xe} ${dr.y - 26}H${lane2}` + (dr === last ? '' : `M${xe} ${dr.y + 26}H${lane2}`), class: 'fl-lane' }, gLane);
        corners += `M${lane2} ${dr.y - 26 - ck}V${dr.y - 26}H${lane2 + ck}`;
        if (dr !== last) corners += `M${lane2} ${dr.y + 26 + ck}V${dr.y + 26}H${lane2 + ck}`;
        // stop bar at the station edge, and a painted arrow pointing into the station
        S('path', { d: `M${xe} ${dr.y - 26}V${dr.y + 26}`, class: 'fl-lane solid' }, gLane);
        const ax = Math.min(xe - 10, lane2 + Math.max(16, (xe - lane2) * 0.62));
        S('path', { d: `M${ax - 8} ${dr.y - 9}L${ax} ${dr.y}L${ax - 8} ${dr.y + 9}`, class: 'fl-arrow' }, gPaint);
        if (xe - lane2 > 60) S('path', { d: `M${ax - 20} ${dr.y - 9}L${ax - 12} ${dr.y}L${ax - 20} ${dr.y + 9}`, class: 'fl-arrow' }, gPaint);
      });
      if (corners) S('path', { d: corners, class: 'fl-lane corner' }, gLane);
      parkY = last ? last.y + top0 : Infinity;
      // direction-of-travel chevrons and WALKWAY stencils in the walkway, away from the doors
      let k = 0;
      for (let y = 560; y < endY - 160; y += 620) {
        if (doors.some(dr => Math.abs(dr.y - y) < 110) || bands.some(b => b.sec && Math.abs(b.top - y) < 70)) continue;
        if (k++ % 2) T('WALKWAY', { x: 0, y: 0, transform: `translate(${laneC - 3.4} ${y}) rotate(90)`, 'text-anchor': 'middle', class: 'fl-walk' }, gPaint);
        else S('path', { d: `M${laneC - 7} ${y - 4}L${laneC} ${y + 3}L${laneC + 7} ${y - 4}M${laneC - 7} ${y + 5}L${laneC} ${y + 12}L${laneC + 7} ${y + 5}`, class: 'fl-arrow thin' }, gPaint);
      }

      // 5. structural columns in the right aisle every 1200px, with dimension lines between them
      // a regular bay (1200px = 12 000 mm on the plan); a column that would stand on a threshold
      // tape is left out rather than nudged, so every dimension reads 12 000 or 24 000
      const step = 1200, cols = [];
      for (let y = 660; y < H - 120; y += step) {
        if (bands.some(b => b.sec && Math.abs(b.top - y) < 40)) continue;
        cols.push(y);
      }
      const GRID = 'ABCDEFGHJKLMNPQRSTUVWXYZ';   // drafting convention: no I or O
      const roomy = aisle >= 140, dimX = colX + 34;
      cols.forEach((y, i) => {
        const g = S('g', { transform: `translate(${colX} ${y})` }, gHw);
        S('rect', { x: -15, y: -15, width: 30, height: 30, rx: 1.5, class: 'fl-plate' }, g);
        [[-10, -10], [10, -10], [-10, 10], [10, 10]].forEach(([x, yb]) => S('circle', { cx: x, cy: yb, r: 1.7, class: 'fl-bolt' }, g));
        S('path', { d: 'M-8 -7H8M-8 7H8M0 -7V7', class: 'fl-beam' }, g);
        // column grid bubble (filled with the band colour so the grid does not run through the letter)
        const lbl = GRID[i % GRID.length];
        if (roomy) S('path', { d: `M-15 0H${-Math.min(34, colX - R - 14) + 9}`, class: 'fl-dim' }, g);
        const bx = -Math.min(34, colX - R - 14);
        if (roomy) { S('circle', { cx: bx, cy: 0, r: 8, class: 'fl-bubble' + (altAt(y) ? ' alt' : '') }, g); T(lbl, { x: bx, y: 3.4, 'text-anchor': 'middle', class: 'fl-bubt' }, g); }
        if (roomy && i < cols.length - 1) {
          const y2 = cols[i + 1], ym = (y + y2) / 2;
          S('path', { d: `M${dimX} ${y}V${ym - 26}M${dimX} ${ym + 26}V${y2}M${dimX - 4} ${y + 4}l8 -8M${dimX - 4} ${y2 + 4}l8 -8M${colX + 17} ${y}H${dimX + 4}M${colX + 17} ${y2}H${dimX + 4}`, class: 'fl-dim', transform: `translate(${-colX} ${-y})` }, g);
          T(((y2 - y) * 10).toLocaleString('en-US').replace(',', ' '), { x: 0, y: 0, transform: `translate(${dimX - colX + 3.5} ${ym - y}) rotate(-90)`, 'text-anchor': 'middle', class: 'fl-dimt' }, g);
        }
      });

      // 6. sparse floor details between columns: keep-clear box, drain grate, anchor bolts
      cols.slice(0, -1).forEach((y, i) => {
        const ym = y + (cols[i + 1] - y) / 2;
        if (bands.some(b => b.sec && Math.abs(b.top - ym) < 120)) return;
        const kind = i % 3;
        const g = S('g', { transform: `translate(${colX} ${Math.round(ym)})` }, i % 3 === 0 ? gPaint : gHw);
        if (kind === 0) {
          const w = Math.min(46, (colX - R - 8) * 2 - 4), h = 120;
          S('rect', { x: -w / 2, y: -h / 2, width: w, height: h, fill: 'url(#flHatch)', class: 'fl-kc-fill' }, g);
          S('rect', { x: -w / 2, y: -h / 2, width: w, height: h, class: 'fl-kc' }, g);
          S('rect', { x: -7, y: -37, width: 14, height: 74, class: 'fl-kc-pad' + (altAt(ym) ? ' alt' : '') }, g);
          T('KEEP CLEAR', { x: 0, y: 0, transform: 'rotate(-90) translate(0 3.6)', 'text-anchor': 'middle', class: 'fl-kct' }, g);
        } else if (kind === 1) {
          S('rect', { x: -14, y: -22, width: 28, height: 44, rx: 2, class: 'fl-plate' }, g);
          let gd = ''; for (let k = -16; k <= 16; k += 4) gd += `M-9 ${k}H9`;
          S('path', { d: gd, class: 'fl-grate' }, g);
        } else gearbox(g, i);
      });
    }

    if (wide) {
      // 7. a gearbox pit in the hero's right aisle, clear of the first column
      const hero = bands.find(b => !b.sec);
      if (hero) {
        const gy = Math.round(Math.min(hero.top + hero.h * 0.42, 560));
        const g = S('g', { transform: `translate(${colX} ${gy})` }, gHw); gearbox(g, 1);
      }
      // 8. gear trains standing in the free strips of both aisles: left between the walkway and the
      //    content, right between the content and the column line. Slots alternate sides down the page
      //    and skip anything they would touch (doors, tape, columns, floor details).
      const lane1 = Math.round(Math.min(Math.max(aisle * 0.38, 30), 96)) - 12, lane2 = lane1 + 24;
      const xe = L - 14, doorsY = bands.filter(b => b.sec).map(b => b.top + b.hMid);
      const strips = [
        { a: lane2 + 10, b: xe - 8, side: 'l' },
        (aisle >= 140 ? { a: R + 14, b: colX - 24, side: 'r' } : { a: R + 12, b: W - 8, side: 'r' }),
      ].map(st => ({ ...st, w: st.b - st.a }));
      const colsY = [];
      for (let y = 660; y < H - 120; y += 1200) if (!bands.some(b => b.sec && Math.abs(b.top - y) < 40)) colsY.push(y);
      const detailY = colsY.slice(0, -1).map((y, i) => y + (colsY[i + 1] - y) / 2);
      const SPECS = [[[1, 0], [.55, 92], [.78, 84]], [[.8, 0], [1, 96], [.5, 80]], [[1, 0], [.62, 86]]];
      let k = 0;
      const pitch = strips.every(t => t.w >= 44) ? 520 : 860;
      for (let y = 380; y < H - 260; y += pitch, k++) {
        let st = strips[k % 2];
        if (st.w < 44) st = strips[(k + 1) % 2];
        if (st.w < 44) continue;
        const D = Math.min(st.w, 76), m = D >= 60 ? 2.6 : 2.1;
        const spec = SPECS[k % 3].map(([f, dir]) => [Math.max(8, Math.round(f * D / m / 2) * 2), dir]);
        const rs = spec.map(([n]) => m * n / 2), span = 2 * rs.reduce((a, b) => a + b, 0) + m * 1.2;
        const top = y - span / 2, bot = y + span / 2;
        const near = (v, pad) => v > top - pad && v < bot + pad;
        if (doorsY.some(d => near(d, 60)) || bands.some(b => b.sec && near(b.top, 50)) || stencils.some(sc => near(sc.b.top + sc.b.hTop / 2, 40))) continue;
        if (st.side === 'r' && (colsY.some(c => near(c, 22)) || detailY.some(d => near(d, 74)))) continue;
        const cx = (st.a + st.b) / 2 - 3;
        trainAt(S('g', {}, gHw), cx, top + rs[0] + m * 0.6, m, spec, 0.12, k % 3 === 1 ? 1 : -1);
      }
      // 9. big gears cropped by the left screen edge, outside the walkway, one per long band
      const big = (lane1 - 12) / 0.66;
      if (big >= 30) {
        bands.forEach((b, i) => {
          const y = Math.round(b.top + Math.min(b.h * 0.6, b.h - 220));
          if (b.h < 600 || doorsY.some(d => Math.abs(d - y) < big + 70) || bands.some(o => o.sec && Math.abs(o.top - y) < big + 40)) return;
          const n = 36, mm = 2 * big / n;
          trainAt(S('g', {}, gHw), -big * 0.34, y, mm, i % 2 ? [[n, 0], [13, -72], [9, -108]] : [[n, 0], [11, 70], [15, 112]], 0.05, 2);
        });
      }
    }
    floor.replaceChildren(svg);
    turn();
    // real stencil bridges: a vertical tie through each closed counter (O, 0, 8, D, P, R, A…), cut in the
    // band colour. Needs the laid-out glyphs, so it runs once the SVG is in the document.
    const bw = Math.max(2.5, r1(fs * 0.05));
    stencils.forEach(({ t, lab, b }) => {
      let d = '';
      try {
        for (let i = 0; i < lab.length; i++) {
          const ch = lab[i]; if (!/[0689ABDOPQR]/.test(ch)) continue;
          const e = t.getExtentOfChar(i); if (!e.width) continue;
          const cx = e.x + e.width * (/[BDPR]/.test(ch) ? 0.58 : 0.5);
          d += `M${r1(cx - bw / 2)} ${r1(e.y)}h${bw}v${r1(e.height)}h${-bw}z`;
        }
      } catch (err) { return; }
      if (d) S('path', { d, class: 'fl-bridge' + (b.alt ? ' alt' : ''), 'clip-path': `url(#flc-${b.id})` }, gBridge);
    });
    if (forklift) { laneX = laneC - 10; forklift.hidden = !wide; place(); }
  }

  let raf = 0;
  const later = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; draw(); }); };
  // redraw inside the observer callback (layout is already clean there), so band fills never lag the content
  new ResizeObserver(() => { cancelAnimationFrame(raf); raf = 0; draw(); }).observe(page);
  addEventListener('resize', later);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(later);
  draw();
}
